import re
from time import time
import discord
import logging
from freedictionaryapi.clients.async_client import AsyncDictionaryApiClient
from freedictionaryapi.errors import DictionaryApiError
from wordfreq import zipf_frequency
from typing import Dict, List, Optional
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.views import SimpleMenu

log = logging.getLogger("red.atnqty-cogs.apropos")

def batched(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

class Apropos(commands.Cog):
    """Detect rarely used words e.g. apropos and show definitions."""

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=4362889)
        self.aprominf: Dict[int, float] = {}
        self.apromaxf: Dict[int, float] = {}
        self.aproall: Dict[int, bool] = {}
        self.aprouids: Dict[int, List[int]] = {}
        self.aprobl: Dict[int, List[str]] = {}
        self.aprocd: Dict[int, int] = {}
        # self.aprocdow: Dict[int, bool] = {}
        self.aprocdict: Dict[int, Dict[str, float]] = {}
        self.aprominlen: Dict[int, int] = {}
        self.config.register_guild(aprominf=1.0, apromaxf=2.7, aproall=False, aprouids=[], aprobl=[], aprocd=604800, aprocdict={}, aprominlen=5)
        self.client = AsyncDictionaryApiClient()
    
    async def cog_load(self):
        all_config = await self.config.all_guilds()
        self.aprominf = {guild_id: conf['aprominf'] for guild_id, conf in all_config.items()}
        self.apromaxf = {guild_id: conf['apromaxf'] for guild_id, conf in all_config.items()}
        self.aproall = {guild_id: conf['aproall'] for guild_id, conf in all_config.items()}
        self.aprouids = {guild_id: conf['aprouids'] for guild_id, conf in all_config.items()}
        self.aprobl = {guild_id: conf['aprobl'] for guild_id, conf in all_config.items()}
        self.aprocd = {guild_id: conf['aprocd'] for guild_id, conf in all_config.items()}
        self.aprocdict = {guild_id: conf['aprocdict'] for guild_id, conf in all_config.items()}
        self.aprominlen = {guild_id: conf['aprominlen'] for guild_id, conf in all_config.items()}

    async def cog_unload(self):
        if self.client:
            await self.client.close()

    # Listeners

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if not await self.is_valid_red_message(message):
            return
        channel_perms = message.channel.permissions_for(message.guild.me)
        if not channel_perms.send_messages:
            return
        if not message.content:
            return
        if message.content.startswith('!'):
            return
        aprouid = self.aprouids.get(message.guild.id, None)
        aproall = self.aproall.get(message.guild.id, None)
        if ((aprouid and (message.author.id in aprouid)) or aproall):
            aprominlen = self.aprominlen.get(message.guild.id, None)
            aprominf = self.aprominf.get(message.guild.id, None)
            apromaxf = self.apromaxf.get(message.guild.id, None)
            # log.info(f"Parsing {message.content}")
            chunks = re.split('[^a-zA-Z]', message.content)
            aproposes = []
            aprobl = self.aprobl.get(message.guild.id, None)
            # for chunk in chunks:
            #     word = ''.join(ch for ch in chunk if ch not in string.punctuation)
            for chunk in chunks:
                if aprominlen and (len(chunk) < aprominlen):
                    continue
                if aprobl and (chunk in aprobl):
                    continue
                zipf=zipf_frequency(chunk, 'en', wordlist='large', minimum=aprominf)
                # log.info(f"{chunk}: {zipf}")
                if aprominf < zipf <= apromaxf:
                    aproposes.append(chunk)
            if aproposes:
                log.info(aproposes)
                # pages = []
                aproposes_real = set()
                # words = worddict.getMeanings(aproposes)
                for word in aproposes:
                    self.aprocdict.setdefault(message.guild.id, {})
                    async with self.config.guild(message.guild).aprocdict() as aprocdict:
                        previous_expiration = 0
                        time_now = time()
                        aprocd = self.aprocd.get(message.guild.id, None)
                        if word in self.aprocdict[message.guild.id]:
                            previous_expiration = self.aprocdict[message.guild.id][word]
                        new_time = max(previous_expiration + aprocd, time_now + aprocd)
                        if (time_now > previous_expiration):
                            aproposes_real.add(word)
                        aprocdict[word] = new_time
                        self.aprocdict[message.guild.id][word] = new_time

                for word in aproposes_real:
                    worddefs = None
                    try:
                        worddefs = await self.client.fetch_word(word)
                    except DictionaryApiError:
                        log.info(f'API error for word {word}')
                    else:
                        msg = f"## {word}"
                        for meaning in worddefs.meanings:
                            msg += f"\n*{meaning.part_of_speech}*\n"
                            i = 1
                            for definition in meaning.definitions:
                                msg += f"{i}. {definition.definition}\n"
                                i += 1
                                # pages.append(f"## {word}\n*{meaning.part_of_speech}*\n{definition.definition}")
                                log.info(f"{word} ({meaning.part_of_speech}): {definition.definition}")
                        await message.reply(content=msg, allowed_mentions=discord.AllowedMentions.none())
                # if not pages:
                #     return
                # elif len(pages) == 1:
                #     await channel.send(content=pages[0])
                # else:
                #     pages.reverse()
                #     for i in range(len(pages)):
                #         pages[i] += f"`Page {i+1}/{len(pages)}`"
                #     ctx: commands.Context = await self.bot.get_context(message)
                #     await SimpleMenu(pages, timeout=3600).start(ctx)                    

    async def is_valid_red_message(self, message: discord.Message) -> bool:
        return await self.bot.allowed_by_whitelist_blacklist(message.author) \
               and await self.bot.ignored_channel_or_guild(message) \
               and not await self.bot.cog_disabled_in_guild(self, message.guild)

    # Commands

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def apropos(self, ctx: commands.Context):
        """Detect rarely used words e.g. apropos and show definitions."""
        await ctx.send_help()

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def minf(self, ctx: commands.Context, minf: Optional[float]):
        """Set the minimum Zipf frequency of words to detect. Default 1.0, lower means rarer words."""
        if minf is None:
            return await ctx.send(f"The current minimum frequency is {self.aprominf.get(ctx.guild.id, None)}")
        await self.config.guild(ctx.guild).aprominf.set(minf)
        self.aprominf[ctx.guild.id] = minf
        await ctx.send(f"✅ The new minimum frequency is {minf}")

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def maxf(self, ctx: commands.Context, maxf: Optional[float]):
        """Set the maximum Zipf frequency of words to detect. Default 2.0, lower means rarer words."""
        if maxf is None:
            return await ctx.send(f"The current maximum frequency is {self.apromaxf.get(ctx.guild.id, None)}")
        await self.config.guild(ctx.guild).apromaxf.set(maxf)
        self.apromaxf[ctx.guild.id] = maxf
        await ctx.send(f"✅ The new maximum frequency is {maxf}")

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def cooldown(self, ctx: commands.Context, cd: Optional[float]):
        """Set cooldown in seconds."""
        if cd is None:
            return await ctx.send(f"The current cooldown is {self.aprocd.get(ctx.guild.id, None)} seconds")
        await self.config.guild(ctx.guild).aprocd.set(cd)
        self.aprocd[ctx.guild.id] = cd
        await ctx.send(f"✅ The new cooldown duration is {cd} seconds")

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def detect(self, ctx: commands.Context):
        """Toggle between detecting all or specific users."""
        toggled_detect = not self.aproall[ctx.guild.id]
        await self.config.guild(ctx.guild).aproall.set(toggled_detect)
        self.aproall[ctx.guild.id] = toggled_detect
        if toggled_detect:
            await ctx.send(f"Now detecting from messages from all users.")
        else:
            await ctx.send(f"Now detecting from messages from selected users.")

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def uidadd(self, ctx: commands.Context, entry: str):
        """Add user ID to detect from."""
        uidstrs = entry.split()
        uids = [int(uidstr) for uidstr in uidstrs if uidstr.isdigit()]
        self.aprouids.setdefault(ctx.guild.id, [])
        async with self.config.guild(ctx.guild).aprouids() as aprouids:
            for uid in uids:
                if not (ctx.guild.get_member(uid)):
                    await ctx.send(f"User ID {uid} not found")
                    continue
                if uid in self.aprouids[ctx.guild.id]:
                    return await ctx.send("UID already exists")
                else:
                    aprouids.append(uid)
                    self.aprouids[ctx.guild.id].append(uid)
                    await ctx.tick(message="UID added")

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def uidremove(self, ctx: commands.Context, entry: str):
        """Remove user ID to detect from."""
        uidstrs = entry.split()
        uids = [int(uidstr) for uidstr in uidstrs if uidstr.isdigit()]
        self.aprouids.setdefault(ctx.guild.id, [])
        async with self.config.guild(ctx.guild).aprouids() as aprouids:
            for uid in uids:
                if not (ctx.guild.get_member(uid)):
                    await ctx.send(f"User ID {uid} not found")
                    continue
                removed = False
                if uid in aprouids:
                    aprouids.remove(uid)
                    removed = True
                if uid in self.aprouids[ctx.guild.id]:
                    self.aprouids[ctx.guild.id].remove(uid)
                    removed = True
                if removed:
                    await ctx.tick(message="UID removed")
                else:
                    await ctx.send("UID not found")

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def uidlist(self, ctx: commands.Context):
        """Shows all user ID to detect from."""
        if ctx.guild.id not in self.aprouids or not self.aprouids[ctx.guild.id]:
            return await ctx.send("None.")
        aprouids = [f"{uid}" for uid in self.aprouids[ctx.guild.id]]
        pages = []
        for i, batch in enumerate(batched(aprouids, 10)):
            embed = discord.Embed(title="Word Detecting UIDs", color=await ctx.embed_color())
            if len(aprouids) > 10:
                embed.set_footer(text=f"Page {i+1}/{(9+len(aprouids))//10}")
            embed.description = '\n'.join(batch)
            pages.append(embed)
        await SimpleMenu(pages, timeout=300).start(ctx)

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def bladd(self, ctx: commands.Context, bl: str):
        """Add word to blacklist."""
        words = re.split('[^a-zA-Z]', bl)
        self.aprobl.setdefault(ctx.guild.id, [])
        async with self.config.guild(ctx.guild).aprobl() as aprobl:
            for word in words:
                # word = ''.join(ch for ch in bl if ch not in string.punctuation)
                if not zipf_frequency(word, "en"):
                    await ctx.send(f"{word} not a word")
                    continue
                if word in self.aprobl[ctx.guild.id]:
                    return await ctx.send(f"Word {word} already in blacklist")
                else:
                    aprobl.append(word)
                    self.aprobl[ctx.guild.id].append(word)
                    await ctx.tick(message=f"Word {word} added to blacklist")

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def blremove(self, ctx: commands.Context, bl: str):
        """Remove word to blacklist."""
        words = re.split('[^a-zA-Z]', bl)
        self.aprobl.setdefault(ctx.guild.id, [])
        async with self.config.guild(ctx.guild).aprobl() as aprobl:
            for word in words:
                # word = ''.join(ch for ch in bl if ch not in string.punctuation)
                if not zipf_frequency(word, "en"):
                    await ctx.send(f"{word} not a word")
                    continue
                removed = False
                if word in aprobl:
                    aprobl.remove(word)
                    removed = True
                if word in self.aprobl[ctx.guild.id]:
                    self.aprobl[ctx.guild.id].remove(word)
                    removed = True
                if removed:
                    await ctx.tick(message=f"Word {word} removed from blacklist")
                else:
                    await ctx.send(f"Word {word} not found in blacklist")

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def blacklist(self, ctx: commands.Context):
        """Shows all words in blacklist."""
        if ctx.guild.id not in self.aprobl or not self.aprobl[ctx.guild.id]:
            return await ctx.send("None.")
        aprobl = self.aprobl[ctx.guild.id]
        pages = []
        for i, batch in enumerate(batched(aprobl, 10)):
            embed = discord.Embed(title="Blacklisted Words", color=await ctx.embed_color())
            if len(aprobl) > 10:
                embed.set_footer(text=f"Page {i+1}/{(9+len(aprobl))//10}")
            embed.description = '\n'.join(batch)
            pages.append(embed)
        await SimpleMenu(pages, timeout=300).start(ctx)

    @apropos.command()
    @commands.has_permissions(manage_guild=True)
    async def minlen(self, ctx: commands.Context, minlen: Optional[float]):
        """Set the minimum length of words to detect. Default 5."""
        if minlen is None:
            return await ctx.send(f"The current minimum length is {self.aprominlen.get(ctx.guild.id, None)}")
        await self.config.guild(ctx.guild).aprominlen.set(minlen)
        self.aprominlen[ctx.guild.id] = minlen
        await ctx.send(f"✅ The new minimum length is {minlen}")

    @commands.command()
    async def zipf(self, ctx: commands.Context, *entries: Optional[str]):
        """Find zipf frequency of words."""
        if not entries:
            await ctx.send_help()
            return
        entry = " ".join(entries)
        words = re.split('[^a-zA-Z]', entry)
        zipfs = [f"{word}: {zipf_frequency(word, 'en', wordlist='large')}" for word in words if word]
        pages = []
        for i, batch in enumerate(batched(zipfs, 10)):
            embed = discord.Embed(title="Zipf Frequency", color=await ctx.embed_color())
            if len(zipfs) > 10:
                embed.set_footer(text=f"Page {i+1}/{(9+len(zipfs))//10}")
            embed.description = '\n'.join(batch)
            pages.append(embed)
        await SimpleMenu(pages, timeout=300).start(ctx)
