import asyncio
import discord
import json

import opendota
import overwatch
import league
import strings as s
import telegram
import bs4
import brawlhalla
import osu

loop = asyncio.get_event_loop()
d_client = discord.Client()
discord_is_ready = False


# When Discord is ready, set discord_is_ready to True
@d_client.event
async def on_ready():
    global discord_is_ready
    discord_is_ready = True

# Get player database from the db.json file
file = open("db.json")
db = json.load(file)
file.close()

# Get the discord bot token from "discordtoken.txt"
file = open("discordtoken.txt", "r")
token = file.read()
file.close()

def save_db():
    """Save the current db object to the db.json file."""
    f = open("db.json", "w")
    json.dump(db, f)
    f.close()
    del f


async def overwatch_status_change(timeout):
    """Check for Overwatch levelups and rank changes."""
    while True:
        if discord_is_ready:
            print("[Overwatch] Starting check...")
            # Update data for every player in list
            for player in db:
                if "overwatch" in db[player]:
                    try:
                        r = await overwatch.get_player_data(**db[player]["overwatch"])
                    except overwatch.NotFoundException:
                        print("[Overwatch] Player not found.")
                    except Exception:
                        # If some other error occours, skip the player
                        print("[Overwatch] Request returned an unhandled exception.")
                    else:
                        # Check for levelups
                        level = r["data"]["level"]
                        try:
                            oldlevel = db[player]["overwatch"]["level"]
                        except KeyError:
                            oldlevel = 0
                        if level > oldlevel:
                            # Send the message
                            loop.create_task(send_event(eventmsg=s.overwatch_level_up, player=player, level=level))
                            # Update database
                            db[player]["overwatch"]["level"] = level
                        # Check for rank changes
                        rank = r["data"]["competitive"]["rank"]
                        if rank is not None:
                            rank = int(rank)
                            try:
                                oldrank = int(db[player]["overwatch"]["rank"])
                            except KeyError:
                                oldrank = 0
                            if rank != oldrank:
                                # Send the message
                                loop.create_task(send_event(eventmsg=s.overwatch_rank_change,
                                                            player=player, change=overwatch.format_rankchange(rank-oldrank),
                                                            rank=rank, medal=overwatch.url_to_medal(r["data"]["competitive"]["rank_img"])))
                                # Update database
                                db[player]["overwatch"]["season"] = 4
                                db[player]["overwatch"]["rank"] = rank
                        else:
                            db[player]["overwatch"]["rank"] = None
                        save_db()
                    finally:
                        await asyncio.sleep(1)
            print("[Overwatch] Check completed successfully.")
            # Wait for the timeout
            await asyncio.sleep(timeout)
        else:
            await asyncio.sleep(1)


async def league_rank_change(timeout):
    """Check for League of Legends solo-duo ranked status changes."""
    while True:
        if discord_is_ready:
            print("[League] Starting check for rank changes...")
            # Update data for every player in list
            for player in db:
                if "league" in db[player]:
                    try:
                        r = await league.get_player_rank(**db[player]["league"])
                    except league.NoRankedGamesCompletedException:
                        # If the player has no ranked games completed, skip him
                        pass
                    except league.RateLimitException:
                        # If you've been ratelimited, skip the player and notify the console.
                        print("[League] Request rejected for rate limit.")
                    except Exception:
                        # If some other error occours, skip the player
                        print("[League] Request returned an unhandled exception.")
                    else:
                        # Convert tier into a number
                        tier_number = league.ranklist.index(r["tier"])
                        roman_number = league.roman.index(r["entries"][0]["division"])  # Potrebbe non funzionare
                        try:
                            old_tier_number = db[player]["league"]["tier"]
                            old_roman_number = db[player]["league"]["division"]
                        except KeyError:
                            # Bronze VI?
                            old_tier_number = 0
                            old_roman_number = 5
                        # Check for tier changes
                        if tier_number != old_tier_number or roman_number != old_roman_number:
                            # Send the message
                            loop.create_task(send_event(eventmsg=s.league_rank_up, player=player, tier=s.league_tier_list[tier_number], division=s.league_roman_list[roman_number],
                                                        oldtier=s.league_tier_list[old_tier_number], olddivision=s.league_roman_list[old_roman_number]))
                            # Update database
                            db[player]["league"]["tier"] = tier_number
                            db[player]["league"]["division"] = roman_number
                            save_db()
                    finally:
                        # Prevent getting ratelimited by Riot
                        await asyncio.sleep(2)
            print("[League] Rank check completed.")
            # Wait for the timeout
            await asyncio.sleep(timeout)
        else:
            await asyncio.sleep(1)


async def league_level_up(timeout):
    """Check for League of Legends profile level ups and name changes."""
    while True:
        if discord_is_ready:
            print("[League] Starting check for level changes...")
            # Update data for every player in list
            for player in db:
                if "league" in db[player]:
                    try:
                        r = await league.get_player_info(**db[player]["league"])
                    except league.RateLimitException:
                        # If you've been ratelimited, skip the player and notify the console.
                        print("[League] Request rejected for rate limit.")
                    except Exception:
                        # If some other error occours, skip the player
                        print("[League] Request returned an unhandled exception.")
                    else:
                        # Update summoner name
                        name = r["name"]
                        db[player]["league"]["name"] = name
                        # Check for level changes
                        level = r["summonerLevel"]
                        try:
                            old_level = db[player]["league"]["level"]
                        except KeyError:
                            old_level = 0
                        if level > old_level:
                            # Send the message
                            loop.create_task(send_event(eventmsg=s.league_level_up, player=player, level=level))
                            # Update database
                            db[player]["league"]["level"] = level
                        save_db()
                    finally:
                        # Prevent getting ratelimited by Riot
                        await asyncio.sleep(2)
            print("[League] Level check completed.")
            # Wait for the timeout
            await asyncio.sleep(timeout)
        else:
            await asyncio.sleep(1)


async def brawlhalla_update_mmr(timeout):
    """Check for Brawlhalla MMR changes."""
    while True:
        if discord_is_ready:
            print("[Brawlhalla] Starting check for mmr changes...")
            # Update mmr for every player in list
            for player in db:
                if "brawlhalla" in db[player]:
                    try:
                        r = await brawlhalla.get_leaderboard_for(db[player]["brawlhalla"]["username"])
                    except None:
                        print("[Brawlhalla] Request returned an unhandled exception.")
                    else:
                        # Parse the page
                        bs = bs4.BeautifulSoup(r.text, "html.parser")
                        # Divide the page into rows
                        rows = bs.find_all("tr")
                        # Find the row containing the rank
                        for row in rows:
                            # Skip header rows
                            if row.has_attr('id') and row['id'] == "rheader":
                                continue
                            # Check if the row belongs to the correct player
                            # (Brawlhalla searches aren't case sensitive)
                            columns = list(row.children)
                            for column in columns:
                                # Find the player name column
                                if column.has_attr('class') and column['class'][0] == "pnameleft":
                                    # Check if the name matches the parameter
                                    if column.string == db[player]["brawlhalla"]["username"]:
                                        break
                            else:
                                continue
                            # Get the current mmr
                            mmr = int(list(row.children)[7].string)
                            try:
                                old_mmr = db[player]["brawlhalla"]["mmr"]
                            except KeyError:
                                old_mmr = 0
                            # Compare the mmr with the value saved in the database
                            if mmr != old_mmr:
                                # Send a message
                                loop.create_task(send_event(s.brawlhalla_new_mmr, player=player, mmr=mmr, oldmmr=old_mmr))
                                # Update database
                                db[player]["brawlhalla"]["mmr"] = mmr
                                save_db()
                            break
                    finally:
                        await asyncio.sleep(1)
            print("[Brawlhalla] Request returned an unhandled exception.")
            await asyncio.sleep(timeout)
        else:
            await asyncio.sleep(1)


async def opendota_last_match(timeout):
    """Check for new played Dota 2 matches using the OpenDota API."""
    while True:
        if discord_is_ready:
            print("[OpenDota] Starting last match check...")
            # Check for new dota match for every player in the database
            for player in db:
                try:
                    # TODO: Se uno non ha mai giocato a dota, cosa succede? Aggiungere handling
                    r = await opendota.get_latest_match(db[player]["steam"]["steamid"])
                except KeyError:
                    continue
                else:
                    try:
                        old_last = db[player]["dota"]["lastmatch"]
                    except KeyError:
                        old_last = 0
                    last = r["match_id"]
                    if last > old_last:
                        # Get player team
                        # 0 if radiant
                        # 1 if dire
                        team = r["player_slot"] & 0b10000000 >> 7
                        # Get victory status
                        victory = (bool(team) == r["radiant_win"])
                        # Prepare format map
                        f = {
                            "k": r["kills"],
                            "d": r["deaths"],
                            "a": r["assists"],
                            "player": player,
                            "result": s.won if victory else s.lost,
                            "hero": opendota.get_hero_name(r["hero_id"])
                        }
                        # Send a message
                        loop.create_task(send_event(s.dota_new_match, **f))
                        # Update database
                        try:
                            db[player]["dota"]["lastmatch"] = last
                        except KeyError:
                            db[player]["dota"] = {
                                "lastmatch": last
                            }
                        save_db()
                finally:
                    await asyncio.sleep(2)
            print("[OpenDota] Check successful.")
            await asyncio.sleep(timeout)
        else:
            await asyncio.sleep(1)


async def osu_pp(timeout):
    """Check for changes in Osu! pp."""
    while True:
        if discord_is_ready:
            print("[Osu!] Starting pp check...")
            for mode in range(0, 4):
                for player in db:
                    try:
                        r = await osu.get_user(db[player]["osu"]["id"], mode)
                    except KeyError:
                        continue
                    except Exception:
                        print("[Osu!] Something is wrong...")
                        continue
                    else:
                        if r["pp_raw"] is not None:
                            pp = float(r["pp_raw"])
                        else:
                            pp = 0
                        if pp != 0:
                            try:
                                old = db[player]["osu"][str(mode)]
                            except KeyError:
                                old = 0
                            if pp != old:
                                db[player]["osu"][str(mode)] = pp
                                f = {
                                    "player": player,
                                    "mode": s.osu_modes[mode],
                                    "pp": int(pp),
                                    "change": int(pp - old)
                                }
                                loop.create_task(send_event(s.osu_pp_change, **f))
                        else:
                            db[player]["osu"][str(mode)] = 0.0
                        save_db()
                    finally:
                        await asyncio.sleep(5)
            print("[Osu!] Check successful.")
            await asyncio.sleep(timeout)
        else:
            await asyncio.sleep(1)


async def send_event(eventmsg: str, player: str, **kwargs):
    """Send a message about a new event on both Telegram and Discord"""
    # Create arguments dict
    mapping = kwargs.copy()
    mapping["eventmsg"] = None
    # Discord
    # The user id is the player argument; convert that into a mention
    mapping["player"] = "<@" + player + ">"
    # Format the event message
    msg = eventmsg.format(**mapping)
    # Send the message
    loop.create_task(d_client.send_message(d_client.get_channel("213655027842154508"), msg))
    # Telegram
    # Find the matching Telegram username inside the db
    mapping["player"] = "@" + db[player]["telegram"]["username"]
    # Convert the Discord Markdown to Telegram Markdown
    msg = eventmsg.replace("**", "*")
    # Format the event message
    msg = msg.format(**mapping)
    # Send the message
    loop.create_task(telegram.send_message(msg, -1001105277904))

loop.create_task(overwatch_status_change(900))
print("[Overwatch] Added level up check to the queue.")

loop.create_task(league_rank_change(900))
print("[League] Added rank change check to the queue.")

loop.create_task(league_level_up(900))
print("[League] Added level change check to the queue.")

#loop.create_task(brawlhalla_update_mmr(7200))
#print("[Brawlhalla] Added mmr change check to the queue.")

#loop.create_task(opendota_last_match(600))
#print("[OpenDota] Added last match check to the queue.")

loop.create_task(osu_pp(1800))
print("[Osu!] Added pp change check to the queue.")

# Run until ^C
try:
    loop.run_until_complete(d_client.start(token))
except KeyboardInterrupt:
    loop.run_until_complete(d_client.logout())
finally:
    loop.close()
