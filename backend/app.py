import os
import json
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
game_state_lock = threading.Lock()
CORS(app, resources={r"/*": {"origins": "*"}})

DATA_FILE = os.path.join(os.path.dirname(__file__), "match_history.json")

CHICAGO_TZ = ZoneInfo("America/Chicago")
UTC_TZ = ZoneInfo("UTC")

TARGET_GAMES = {
    # 🎂 bday counter
    "9/11_AM": {"hour": 9, "minute": 11, "counters": ["bday"]},
    "11/11_AM": {"hour": 11, "minute": 11, "counters": ["bday"]},
    "mit_bday": {"hour": 14, "minute": 20, "counters": ["bday"]},
    "ave_bday": {"hour": 15, "minute": 12, "counters": ["bday", "three_pm_games"]},
    "420": {"hour": 16, "minute": 20, "counters": ["bday"]},
    "ca": {"hour": 17, "minute": 30, "counters": ["bday"]},
    "pa": {"hour": 18, "minute": 10, "counters": ["bday"]},
    "9/11_PM": {"hour": 21, "minute": 11, "counters": ["bday"]},
    "11/11_PM": {"hour": 23, "minute": 11, "counters": ["bday"]},
    # 🕛 noon games counter
    "christmas_eve": {"hour": 12, "minute": 24, "counters": ["noon_games"]},
    "christmas_day": {"hour": 12, "minute": 25, "counters": ["noon_games"]},
    "new_years_eve": {"hour": 12, "minute": 31, "counters": ["noon_games"]},
    "1234": {"hour": 12, "minute": 34, "counters": ["noon_games"]},
    # 🕒 3pm games counter (also includes ave_bday)
    "pie": {"hour": 15, "minute": 14, "counters": ["three_pm_games"]},
    "john": {"hour": 15, "minute": 16, "counters": ["three_pm_games"]},
    "321": {"hour": 15, "minute": 21, "counters": ["three_pm_games"]},
    # 🏁 other counters
    "first_date_AM": {"hour": 9, "minute": 24, "counters": ["first_date_AM"]},
    "anniversary_AM": {"hour": 10, "minute": 24, "counters": ["anniversary_AM"]},
    "wwf2": {"hour": 13, "minute": 0, "counters": ["wwf2"]},
    "210": {"hour": 14, "minute": 10, "counters": ["210"]},
    "toad": {"hour": 17, "minute": 24, "counters": ["toad"]},
    "7/11": {"hour": 19, "minute": 11, "counters": ["seven_eleven"]},
    "first_date_PM": {"hour": 21, "minute": 24, "counters": ["first_date_PM"]},
    "anniversary_PM": {"hour": 22, "minute": 24, "counters": ["anniversary_PM"]},
}

COUNTER_MAX_POINTS = {"bday": 9, "noon_games": 4, "three_pm_games": 4}


def create_fresh_game_state():
    return {
        "matches": {},
        "scores": {"Avery": 0, "Mitchell": 0},
        "antsy_penalties": {"Avery": 0, "Mitchell": 0},
        "counter_scores": {
            "bday": {"Avery": 0, "Mitchell": 0},
            "noon_games": {"Avery": 0, "Mitchell": 0},
            "three_pm_games": {"Avery": 0, "Mitchell": 0},
        },
        "closed_counters": [],
        "last_local_date": None,
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        data = create_fresh_game_state()
        save_data(data)
        return data

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def reset_if_new_day(game_state, current_date):
    """
    Reset the game state when the authoritative phone-local
    calendar date changes.
    """
    previous_date = game_state.get("last_local_date")

    if previous_date and previous_date != current_date:

        print("\n" + "🌙" * 15)
        print(" 🌙 NEW GAME DAY DETECTED")
        print(f" Previous date: {previous_date}")
        print(f" Current date:  {current_date}")
        print(" Resetting daily game state.")
        print("🌙" * 15 + "\n")

        game_state = create_fresh_game_state()

    game_state["last_local_date"] = current_date

    save_data(game_state)

    return game_state


def check_mathematical_elimination(game_state):
    """
    Dynamically calculates if a sub-counter group
    is mathematically impossible to win.
    """

    for counter, max_slots in COUNTER_MAX_POINTS.items():

        if counter in game_state.get("closed_counters", []):
            continue

        scores = game_state["counter_scores"].get(counter, {"Avery": 0, "Mitchell": 0})

        ave_score = scores.get("Avery", 0)
        mit_score = scores.get("Mitchell", 0)

        slots_played = 0

        for m_id, m_data in game_state["matches"].items():

            if m_id in TARGET_GAMES:

                if counter in TARGET_GAMES[m_id]["counters"]:

                    if "winner" in m_data:
                        slots_played += 1

        remaining_slots = max_slots - slots_played

        if ave_score > (mit_score + remaining_slots):

            game_state["closed_counters"].append(counter)

            print(
                f"🔒 COUNTER LOCKED: "
                f"{counter.upper()} is mathematically FINAL. "
                f"Avery wins the bracket!"
            )

        elif mit_score > (ave_score + remaining_slots):

            game_state["closed_counters"].append(counter)

            print(
                f"🔒 COUNTER LOCKED: "
                f"{counter.upper()} is mathematically FINAL. "
                f"Mitchell wins the bracket!"
            )


def parse_sent_at(sent_at_raw):
    """
    Parse the iPhone's timezone-aware ISO-8601 timestamp.

    Expected example:

        2026-09-25T12:52:19.453-05:00

    Also accepts:

        2026-09-25T12:52:19-05:00
        2026-09-25T17:52:19.453Z
    """

    if not isinstance(sent_at_raw, str):
        raise ValueError("sent_at must be a string.")

    sent_at_raw = sent_at_raw.strip()

    if not sent_at_raw:
        raise ValueError("sent_at cannot be empty.")

    normalized = sent_at_raw

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    dt = datetime.fromisoformat(normalized)

    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(
            "sent_at must include a timezone offset, " "for example -05:00."
        )

    return dt


def determine_game(local_dt):
    """
    Determine whether the phone's local timestamp is:

    1. The exact final second before a game = ANTSY
    2. Inside the game's target minute = NORMAL
    3. Outside all game windows

    The game clock is always based on the phone's
    own local timezone.
    """

    for game_name, target in TARGET_GAMES.items():

        target_hour = target["hour"]
        target_minute = target["minute"]

        if local_dt.hour == target_hour and local_dt.minute == target_minute:
            return game_name, False

        if (
            local_dt.hour == target_hour
            and local_dt.minute == target_minute - 1
            and local_dt.second == 59
        ):
            return game_name, True

        if target_minute == 0:

            previous_hour = (target_hour - 1) % 24

            if (
                local_dt.hour == previous_hour
                and local_dt.minute == 59
                and local_dt.second == 59
            ):
                return game_name, True

    return None, False


@app.route("/text-drop", methods=["POST"])
def text_drop():

    payload = request.get_json(silent=True)

    print("\n" + "=" * 70)
    print("📡 INCOMING TEXT-DROP")
    print("=" * 70)

    print("📦 RAW PAYLOAD:")
    print(json.dumps(payload, indent=4, default=str))

    if not isinstance(payload, dict):
        print("❌ INVALID PAYLOAD: expected JSON object.")

        return jsonify({"status": "error", "reason": "Expected JSON object."}), 400

    raw_sender = str(payload.get("sender", "")).strip()

    text_content = payload.get("text")

    sender_map = {
        "avery": "Avery",
        "mitchell": "Mitchell",
        "mitchell <3": "Mitchell",
    }

    sender = sender_map.get(raw_sender.lower())

    if sender is None:

        print(f"❌ UNKNOWN SENDER: " f"{raw_sender!r}")

        return (
            jsonify({"status": "error", "reason": f"Unknown sender: {raw_sender!r}"}),
            400,
        )

    print(f"✅ NORMALIZED SENDER: " f"{raw_sender!r} → {sender!r}")

    sent_at_raw = payload.get("sent_at")

    print("\n🕐 INCOMING TIME FIELDS")
    print(f"   sender:       {sender}")
    print(f"   sent_at:      {sent_at_raw!r}")
    print(f"   local_time:   {payload.get('local_time')!r}")

    legacy_timestamp = payload.get("timestamp")

    if legacy_timestamp is not None:
        print(f"   ⚠️ LEGACY timestamp also present: " f"{legacy_timestamp!r}")
        print("   ⚠️ It will NOT be used for game timing.")

    if not sent_at_raw:

        print("❌ MISSING sent_at. " "The iPhone must send a timezone-aware sent_at.")

        return (
            jsonify(
                {
                    "status": "error",
                    "reason": (
                        "Missing sent_at. "
                        "Expected e.g. "
                        "2026-09-25T12:52:19.453-05:00"
                    ),
                }
            ),
            400,
        )

    try:

        sent_at_dt = parse_sent_at(sent_at_raw)

    except ValueError as e:

        print(f"❌ INVALID sent_at: {e}")

        return jsonify({"status": "error", "reason": str(e)}), 400

    sent_at_utc = sent_at_dt.astimezone(UTC_TZ)

    sent_at_chicago = sent_at_dt.astimezone(CHICAGO_TZ)

    sent_at_local = sent_at_dt

    sent_at_ms = int(round(sent_at_dt.timestamp() * 1000))

    server_received = datetime.now(CHICAGO_TZ)

    receipt_delay_seconds = (server_received - sent_at_chicago).total_seconds()

    print("\n" + "-" * 70)
    print("📱 AUTHORITATIVE PHONE TIMESTAMP")
    print("-" * 70)

    print(f"   raw sent_at:       {sent_at_raw}")

    print(f"   parsed timestamp:  " f"{sent_at_dt.isoformat()}")

    print(
        f"   timestamp UTC:     " f"{sent_at_utc.strftime('%Y-%m-%d %H:%M:%S.%f %Z')}"
    )

    print(
        f"   timestamp Chicago: "
        f"{sent_at_chicago.strftime('%Y-%m-%d %H:%M:%S.%f %Z')}"
    )

    print(f"   timestamp ms:      " f"{sent_at_ms}")

    print(f"   payload local_time:" f" {payload.get('local_time')}")

    print(
        f"   server received:   "
        f"{server_received.strftime('%Y-%m-%d %H:%M:%S.%f %Z')}"
    )

    print(f"   receipt delay:     " f"{receipt_delay_seconds:.3f}s")

    print("-" * 70)

    local_time = payload.get("local_time")

    if not local_time:

        print("⚠️ WARNING: local_time is missing.")

    else:

        try:

            local_time_dt = datetime.strptime(local_time, "%H:%M:%S")

            authoritative_time_only = sent_at_dt.strftime("%H:%M:%S")

            print("\n🔍 PHONE TIME CONSISTENCY CHECK")

            print(f"   payload local_time: " f"{local_time}")

            print(f"   sent_at local:      " f"{authoritative_time_only}")

            if local_time_dt.strftime("%H:%M:%S") == authoritative_time_only:

                print("   ✅ local_time AGREES with sent_at.")

            else:

                print("   🚨 MISMATCH!")

                print(f"   local_time says: " f"{local_time}")

                print(f"   sent_at says:    " f"{authoritative_time_only}")

        except ValueError:

            print(f"⚠️ INVALID local_time: " f"{local_time!r}")

    current_hour = sent_at_local.hour
    current_minute = sent_at_local.minute
    current_second = sent_at_local.second
    current_microsecond = sent_at_local.microsecond

    print("\n🕐 AUTHORITATIVE GAME CLOCK")

    print(
        f"   phone local time: " f"{sent_at_local.strftime('%Y-%m-%d %H:%M:%S.%f %Z')}"
    )

    print(f"   hour:         {current_hour}")

    print(f"   minute:       {current_minute}")

    print(f"   second:       {current_second}")

    print(f"   millisecond:  " f"{current_microsecond // 1000:03d}")

    matched_game, is_antsy = determine_game(sent_at_local)

    print(
        f"🧪 TIMING DEBUG: "
        f"sent_at={sent_at_dt.isoformat()} | "
        f"Chicago={sent_at_chicago.strftime('%H:%M:%S.%f %Z')} | "
        f"matched={matched_game} | "
        f"antsy={is_antsy}"
    )

    if matched_game:

        target = TARGET_GAMES[matched_game]

        target_label = f"{target['hour']:02d}:" f"{target['minute']:02d}:00"

        actual_label = (
            f"{current_hour:02d}:"
            f"{current_minute:02d}:"
            f"{current_second:02d}."
            f"{current_microsecond // 1000:03d}"
        )

        print("\n🎯 GAME MATCH")

        print(f"   game:       {matched_game.upper()}")

        print(f"   game start: {target_label}")

        print(f"   actual:     {actual_label}")

        print(f"   status:     " f"{'🐜 ANTSY' if is_antsy else '✅ NORMAL'}")

        if is_antsy:

            print(
                f"🐜 ANTSY: timestamp was "
                f"{actual_label}, "
                f"game begins {target_label}"
            )

    else:

        print("\n❌ NO GAME MATCHED")

        print(
            f"   authoritative Chicago time: "
            f"{sent_at_chicago.strftime('%H:%M:%S.%f')}"
        )

        print("   Game determination is based ONLY " "on sent_at.")

        return (
            jsonify(
                {
                    "status": "ignored",
                    "reason": "Outside game windows.",
                    "sent_at": sent_at_dt.isoformat(),
                    "sent_at_chicago": sent_at_chicago.isoformat(),
                }
            ),
            200,
        )

    counters = TARGET_GAMES[matched_game]["counters"]

    if is_antsy:

        with game_state_lock:

            game_state = load_data()

            game_state = reset_if_new_day(
                game_state, sent_at_local.strftime("%Y-%m-%d")
            )

            for counter in counters:

                if counter in game_state.get("closed_counters", []):

                    print(f"🔒 ANTSY IGNORED: " f"{counter} bracket already finalized.")

                    return (
                        jsonify(
                            {
                                "status": "ignored",
                                "reason": (
                                    f"Bracket {counter} is "
                                    f"mathematically finalized. "
                                    f"Game over."
                                ),
                            }
                        ),
                        200,
                    )

            if matched_game not in game_state["matches"]:
                game_state["matches"][matched_game] = {}

            match_data = game_state["matches"][matched_game]

            if "antsy_players" not in match_data:
                match_data["antsy_players"] = {}

            if sender not in match_data["antsy_players"]:
                match_data["antsy_players"][sender] = []

            match_data["antsy_players"][sender].append(
                {
                    "sent_at": sent_at_dt.isoformat(),
                    "timestamp_ms": sent_at_ms,
                    "readable_time": sent_at_chicago.strftime(
                        "%Y-%m-%d %H:%M:%S.%f %Z"
                    ),
                    "payload_local_time": local_time,
                    "text": text_content,
                }
            )

            game_state["antsy_penalties"][sender] += 1

            game_state["scores"][sender] -= 1

            # Apply -1 to EVERY parent counter.
            #
            # Example:
            #
            # ave_bday has:
            # ["bday", "three_pm_games"]
            #
            # Therefore an Avery antsy violation
            # affects both counters.

            for counter in counters:

                if counter not in game_state["counter_scores"]:

                    game_state["counter_scores"][counter] = {"Avery": 0, "Mitchell": 0}

                game_state["counter_scores"][counter][sender] -= 1

            check_mathematical_elimination(game_state)

            print("\n" + "🚨" * 15)

            print(f"🚨 ANTSY VIOLATION: {sender}")

            print(f"   Game: {matched_game.upper()}")

            print(
                f"   Sent at: " f"{sent_at_chicago.strftime('%Y-%m-%d %H:%M:%S.%f %Z')}"
            )

            print(
                f"   Game begins: "
                f"{target['hour']:02d}:"
                f"{target['minute']:02d}:00"
            )

            print(f"   -1 applied to groups: " f"{', '.join(counters)}")

            print(
                f"   Total antsy violations: "
                f"{game_state['antsy_penalties'][sender]}"
            )

            print("🚨" * 15 + "\n")

            save_data(game_state)

            return (
                jsonify(
                    {
                        "status": "received",
                        "result": "antsy_penalty",
                        "sender": sender,
                        "game": matched_game,
                        "sent_at": sent_at_dt.isoformat(),
                        "sent_at_chicago": sent_at_chicago.isoformat(),
                    }
                ),
                200,
            )

    with game_state_lock:

        game_state = load_data()

        game_state = reset_if_new_day(game_state, sent_at_local.strftime("%Y-%m-%d"))

        for counter in counters:

            if counter in game_state.get("closed_counters", []):

                print(f"🔒 GAME IGNORED: " f"{counter} bracket already finalized.")

                return (
                    jsonify(
                        {
                            "status": "ignored",
                            "reason": (
                                f"Bracket {counter} is "
                                f"mathematically finalized. "
                                f"Game over."
                            ),
                        }
                    ),
                    200,
                )

        if matched_game not in game_state["matches"]:

            game_state["matches"][matched_game] = {}

        match_data = game_state["matches"][matched_game]

        if sender in match_data:

            print(f"⚠️ {sender} already submitted " f"for {matched_game.upper()}.")

            save_data(game_state)

            return (
                jsonify(
                    {
                        "status": "received",
                        "result": "duplicate_submission",
                        "sender": sender,
                        "game": matched_game,
                    }
                ),
                200,
            )

        match_data[sender] = {
            "sent_at": sent_at_dt.isoformat(),
            "timestamp_ms": sent_at_ms,
            "readable_time": sent_at_chicago.strftime("%Y-%m-%d %H:%M:%S.%f %Z"),
            "payload_local_time": local_time,
            "text": text_content,
        }

        print(f"\n💾 RECORDED {sender} FOR " f"{matched_game.upper()}")

        print(f"   sent_at: {sent_at_dt.isoformat()}")

        print(f"   timestamp_ms: {sent_at_ms}")

        players_submitted = []

        if "Avery" in match_data:
            players_submitted.append("Avery")

        if "Mitchell" in match_data:
            players_submitted.append("Mitchell")

        if len(players_submitted) == 1:

            winner = players_submitted[0]

            winner_ms = match_data[winner]["timestamp_ms"]

            match_data["winner"] = winner

            match_data["winner_timestamp_ms"] = winner_ms

            match_data["winner_sent_at"] = match_data[winner]["sent_at"]

            match_data["winner_readable_time"] = match_data[winner]["readable_time"]

            match_data["winner_text"] = match_data[winner]["text"]

            match_data["winner_reason"] = "provisional_first_received"

            game_state["scores"][winner] += 1

            for counter in counters:

                if counter not in game_state["counter_scores"]:

                    game_state["counter_scores"][counter] = {"Avery": 0, "Mitchell": 0}

                game_state["counter_scores"][counter][winner] += 1

            save_data(game_state)

            print("\n" + "🏆" * 15)

            print(f"🏆 PROVISIONAL WINNER: {winner}")

            print(f"🎯 GAME: {matched_game.upper()}")

            print("📲 Only one player's message " "has arrived.")

            print("📱 Point awarded immediately.")

            print(
                "⚠️ If the other player's sent_at "
                "is earlier, the point will transfer."
            )

            print("🏆" * 15 + "\n")

            return (
                jsonify(
                    {
                        "status": "received",
                        "result": "provisional_winner",
                        "winner": winner,
                        "game": matched_game,
                        "winner_sent_at": match_data[winner]["sent_at"],
                        "winner_timestamp_ms": winner_ms,
                    }
                ),
                200,
            )

        avery_ms = match_data["Avery"]["timestamp_ms"]

        mitchell_ms = match_data["Mitchell"]["timestamp_ms"]

        if avery_ms < mitchell_ms:

            winner = "Avery"

        elif mitchell_ms < avery_ms:

            winner = "Mitchell"

        else:

            winner = "Avery"

            print("⚠️ EXACT TIMESTAMP TIE. " "Defaulting to Avery.")

        winner_ms = match_data[winner]["timestamp_ms"]

        previous_winner = match_data.get("winner")

        if previous_winner == winner:

            match_data["winner"] = winner

            match_data["winner_timestamp_ms"] = winner_ms

            match_data["winner_sent_at"] = match_data[winner]["sent_at"]

            match_data["winner_readable_time"] = match_data[winner]["readable_time"]

            match_data["winner_text"] = match_data[winner]["text"]

            match_data["winner_reason"] = "earlier_sent_at_confirmed"

            check_mathematical_elimination(game_state)

            save_data(game_state)

            print("\n" + "🏆" * 15)

            print(f"🏆 GAME WINNER: {winner}")

            print(f"🎯 GAME: {matched_game.upper()}")

            print(f"📱 Avery: " f"{match_data['Avery']['readable_time']}")

            print(f"📱 Mitchell: " f"{match_data['Mitchell']['readable_time']}")

            print("📲 WINNER DETERMINED BY " "IPHONE MESSAGE ORDER")

            print(f"⬆️ FIRST/UPPER MESSAGE: {winner}")

            print("🏆" * 15 + "\n")

            return (
                jsonify(
                    {
                        "status": "received",
                        "result": "winner_confirmed",
                        "winner": winner,
                        "game": matched_game,
                        "winner_sent_at": match_data[winner]["sent_at"],
                        "winner_timestamp_ms": winner_ms,
                    }
                ),
                200,
            )

        print("\n" + "🔄" * 15)

        print("🔄 WINNER CHANGED " "BASED ON MESSAGE ORDER")

        print(f"   Previous winner: " f"{previous_winner}")

        print(f"   New winner: " f"{winner}")

        print(f"   Avery sent_at: " f"{match_data['Avery']['sent_at']}")

        print(f"   Mitchell sent_at: " f"{match_data['Mitchell']['sent_at']}")

        if previous_winner is not None:

            game_state["scores"][previous_winner] -= 1

            for counter in counters:

                if counter not in game_state["counter_scores"]:

                    game_state["counter_scores"][counter] = {"Avery": 0, "Mitchell": 0}

                game_state["counter_scores"][counter][previous_winner] -= 1

        game_state["scores"][winner] += 1

        for counter in counters:

            if counter not in game_state["counter_scores"]:

                game_state["counter_scores"][counter] = {"Avery": 0, "Mitchell": 0}

            game_state["counter_scores"][counter][winner] += 1

        match_data["winner"] = winner

        match_data["winner_timestamp_ms"] = winner_ms

        match_data["winner_sent_at"] = match_data[winner]["sent_at"]

        match_data["winner_readable_time"] = match_data[winner]["readable_time"]

        match_data["winner_text"] = match_data[winner]["text"]

        match_data["winner_reason"] = "earlier_sent_at_overrode_provisional_winner"

        check_mathematical_elimination(game_state)

        save_data(game_state)

        print(f"   🔄 Point transferred " f"{previous_winner} → {winner}")

        print("🔄" * 15 + "\n")

        return (
            jsonify(
                {
                    "status": "received",
                    "result": "winner_changed",
                    "winner": winner,
                    "previous_winner": previous_winner,
                    "game": matched_game,
                    "winner_sent_at": match_data[winner]["sent_at"],
                    "winner_timestamp_ms": winner_ms,
                }
            ),
            200,
        )


@app.route("/get-scoreboard", methods=["GET"])
def get_scoreboard():
    with game_state_lock:
        game_state = load_data()
    return jsonify(game_state), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
