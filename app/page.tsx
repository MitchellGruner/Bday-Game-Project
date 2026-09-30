"use client";

import { useEffect, useState } from "react";

interface PlayerScores {
  Avery: number;
  Mitchell: number;
}

interface MatchEntry {
  winner?: string | null;
  sent_at?: string;
  timestamp_ms?: number;
  readable_time?: string;
  payload_local_time?: string;
  text?: string;
  margin_ms?: number;

  resolved?: boolean;
  winner_reason?: string;
  winner_timestamp_ms?: number | null;
  winner_sent_at?: string | null;
  winner_readable_time?: string | null;
  winner_text?: string | null;

  Avery?: { readable_time: string; text: string };
  Mitchell?: { readable_time: string; text: string };
}

interface ScoreboardData {
  scores: PlayerScores;
  antsy_penalties: PlayerScores;
  counter_scores: {
    bday?: PlayerScores;
    noon_games?: PlayerScores;
    three_pm_games?: PlayerScores;
    "7/11"?: PlayerScores;
  };
  matches: Record<string, MatchEntry>;
  closed_counters?: string[];
}

const GAME_TIMES: Record<string, { hr: number; min: number }> = {
  wwf2: { hr: 13, min: 0 },
  "210": { hr: 14, min: 10 },
  toad: { hr: 17, min: 24 },
  "7/11": { hr: 19, min: 11 },
};

const NOON_GAME_TIMES = [
  { hr: 12, min: 24, name: "Christmas Eve" },
  { hr: 12, min: 25, name: "Christmas Day" },
  { hr: 12, min: 31, name: "New Year's Eve" },
  { hr: 12, min: 34, name: "12:34" },
];

const THREE_PM_GAME_TIMES = [
  { hr: 15, min: 12, name: "Ave Birthday" },
  { hr: 15, min: 14, name: "Pie" },
  { hr: 15, min: 16, name: "John" },
  { hr: 15, min: 21, name: "3-2-1" },
];

export default function Dashboard() {
  const [data, setData] = useState<ScoreboardData | null>(null);
  const [now, setNow] = useState<Date | null>(null);
  const [timeStr, setTimeStr] = useState<Record<string, string>>({});

  useEffect(() => {
    async function fetchScores() {
      try {
        const res = await fetch("http://localhost:5000/get-scoreboard");

        if (res.ok) {
          const json: ScoreboardData = await res.json();
          setData(json);
        }
      } catch (err) {
        console.error("Dashboard failed to sync with Python api stream", err);
      }
    }

    fetchScores();

    const interval = setInterval(fetchScores, 2000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setNow(new Date());

    const timer = setInterval(() => {
      setNow(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const getTodayNextGroupGame = (
    games: { hr: number; min: number; name: string }[],
    now: Date
  ) => {
    for (const game of games) {
      const target = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        game.hr,
        game.min,
        0
      );

      if (now < target) {
        return {
          ...game,
          target,
        };
      }
    }

    return null;
  };

  const getCountdownString = (target: Date, now: Date) => {
    const deltaMs = target.getTime() - now.getTime();

    const hrs = Math.floor(deltaMs / (1000 * 60 * 60));

    const mins = Math.floor((deltaMs % (1000 * 60 * 60)) / (1000 * 60));

    const secs = Math.floor((deltaMs % (1000 * 60)) / 1000);

    return `${hrs}h ${mins}m ${secs}s`;
  };

  const getTodayCountdown = (
    hr: number,
    min: number,
    now: Date
  ): string | null => {
    const target = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      hr,
      min,
      0
    );

    if (now >= target) {
      return null;
    }

    return getCountdownString(target, now);
  };

  useEffect(() => {
    if (!now) {
      setTimeStr({});
      return;
    }

    const updatedClocks: Record<string, string> = {};

    Object.entries(GAME_TIMES).forEach(([key, target]) => {
      const countdown = getTodayCountdown(target.hr, target.min, now);

      if (countdown) {
        updatedClocks[key] = countdown;
      }
    });

    const nextNoonGame = getTodayNextGroupGame(NOON_GAME_TIMES, now);

    if (nextNoonGame) {
      updatedClocks["noon_games"] = getCountdownString(
        nextNoonGame.target,
        now
      );
    }

    const nextThreePmGame = getTodayNextGroupGame(THREE_PM_GAME_TIMES, now);

    if (nextThreePmGame) {
      updatedClocks["three_pm_games"] = getCountdownString(
        nextThreePmGame.target,
        now
      );
    }

    setTimeStr(updatedClocks);
  }, [now]);

  if (!now) {
    return (
      <main className="flex min-h-screen flex-col items-center bg-[#0d1117] p-6 text-[#c9d1d9] select-none">
        <h1 className="mt-4 mb-1 text-4xl font-extrabold tracking-widest text-[#58a6ff] uppercase">
          ⚡ THE BIRTHDAY GAME ⚡
        </h1>

        <p className="mb-8 text-sm text-[#8b949e] italic">
          Live Next.js TypeScript Dashboard
        </p>
      </main>
    );
  }

  const bday: PlayerScores = data?.counter_scores?.bday ?? {
    Avery: 0,
    Mitchell: 0,
  };

  const noon: PlayerScores = data?.counter_scores?.noon_games ?? {
    Avery: 0,
    Mitchell: 0,
  };

  const pm3: PlayerScores = data?.counter_scores?.three_pm_games ?? {
    Avery: 0,
    Mitchell: 0,
  };

  const penalties: PlayerScores = data?.antsy_penalties ?? {
    Avery: 0,
    Mitchell: 0,
  };

  const matches: Record<string, MatchEntry> = data?.matches ?? {};

  const closedCounters = data?.closed_counters ?? [];

  const scores: PlayerScores = bday;

  const getAmPmGameDisplay = (
    amKey: string,
    pmKey: string,
    amHr: number,
    pmHr: number,
    minute: number
  ) => {
    const amMatch = matches[amKey];
    const pmMatch = matches[pmKey];

    const amResolved = amMatch?.resolved === true;

    const pmResolved = pmMatch?.resolved === true;

    const amWinner = amMatch?.winner;
    const pmWinner = pmMatch?.winner;

    const amTarget = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      amHr,
      minute,
      0
    );

    const pmTarget = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      pmHr,
      minute,
      0
    );

    if (!amResolved && now < amTarget) {
      return <>⏳ {getCountdownString(amTarget, now)}</>;
    }

    if (amResolved && !pmResolved && now < pmTarget) {
      return (
        <>
          <div>
            {amWinner ?? "Tie"} <span className="text-xs">(AM)</span>
            {amWinner ? " 🏆" : " 🤝"}
          </div>

          <div className="mt-1">⏳ {getCountdownString(pmTarget, now)}</div>
        </>
      );
    }

    if (!amResolved && !pmResolved && now >= amTarget && now < pmTarget) {
      return (
        <>
          <div className="text-xs text-[#8b949e]">AM: No result</div>

          <div className="mt-1">⏳ {getCountdownString(pmTarget, now)}</div>
        </>
      );
    }

    if (now >= pmTarget) {
      return (
        <>
          <div>
            {amResolved ? (amWinner ?? "Tie") : "No result"}{" "}
            <span className="text-xs">(AM)</span>
            {amResolved ? (amWinner ? " 🏆" : " 🤝") : ""}
          </div>

          <div className="mt-1">
            {pmResolved ? (pmWinner ?? "Tie") : "No result"}{" "}
            <span className="text-xs">(PM)</span>
            {pmResolved ? (pmWinner ? " 🏆" : " 🤝") : ""}
          </div>
        </>
      );
    }

    return "Pending...";
  };

  const getStandaloneWinner = (matchKey: string, timeKey: string) => {
    const match = matches[matchKey];

    if (match?.resolved === true) {
      return match.winner ? `${match.winner} 🏆` : "Tie 🤝";
    }

    if (timeStr[timeKey]) {
      return `⏳ ${timeStr[timeKey]}`;
    }

    return "Awaiting result...";
  };

  const firstDateWinner = getAmPmGameDisplay(
    "first_date_AM",
    "first_date_PM",
    9,
    21,
    24
  );

  const anniversaryWinner = getAmPmGameDisplay(
    "anniversary_AM",
    "anniversary_PM",
    10,
    22,
    24
  );

  const wwf2Winner = getStandaloneWinner("wwf2", "wwf2");

  const game210Winner = getStandaloneWinner("210", "210");

  const toadWinner = getStandaloneWinner("toad", "toad");

  const sevenElevenWinner = getStandaloneWinner("7/11", "7/11");

  const formatGroupCounter = (
    counterKey: string,
    scoreObj: PlayerScores,
    maxPoints: number,
    timeKey: string
  ) => {
    const groupGameKeys =
      counterKey === "noon_games"
        ? ["christmas_eve", "christmas_day", "new_years_eve", "1234"]
        : ["ave_bday", "pie", "john", "321"];

    const slotsPlayed = groupGameKeys.filter(
      (gameKey) => matches[gameKey]?.resolved === true
    ).length;

    const allGamesPlayed = slotsPlayed === maxPoints;

    const remainingSlots = maxPoints - slotsPlayed;

    const isClosed =
      closedCounters.includes(counterKey) ||
      scoreObj.Mitchell > scoreObj.Avery + remainingSlots ||
      scoreObj.Avery > scoreObj.Mitchell + remainingSlots;

    if (isClosed || allGamesPlayed) {
      const winnerName =
        scoreObj.Mitchell > scoreObj.Avery
          ? "Mitchell"
          : scoreObj.Avery > scoreObj.Mitchell
            ? "Avery"
            : "Tie";

      const high = Math.max(scoreObj.Mitchell, scoreObj.Avery);

      const low = Math.min(scoreObj.Mitchell, scoreObj.Avery);

      return {
        text:
          winnerName === "Tie"
            ? `Tie (${high}-${low})`
            : `${winnerName} (${high}-${low}) 🏆`,
        activeStyle: "text-[#58a6ff] font-bold",
      };
    }

    return {
      text: `Avery: ${scoreObj.Avery} | Mitchell: ${scoreObj.Mitchell} (⏳ ${timeStr[timeKey] || "..."})`,
      activeStyle: "text-[#8b949e] font-mono text-sm",
    };
  };

  const noonDisplay = formatGroupCounter("noon_games", noon, 4, "noon_games");

  const pm3Display = formatGroupCounter(
    "three_pm_games",
    pm3,
    4,
    "three_pm_games"
  );

  return (
    <main className="flex min-h-screen flex-col items-center bg-[#0d1117] p-6 text-[#c9d1d9] select-none">
      <h1 className="mt-4 mb-1 text-4xl font-extrabold tracking-widest text-[#58a6ff] uppercase">
        ⚡ THE BIRTHDAY GAME ⚡
      </h1>

      <p className="mb-8 text-sm text-[#8b949e] italic">
        Live Next.js TypeScript Dashboard
      </p>

      <div className="mb-10 flex items-center gap-12 rounded-2xl border-2 border-[#30363d] bg-[#161b22] px-16 py-6 shadow-2xl">
        <div className="text-center">
          <div className="text-2xl font-bold text-[#f0f6fc]">Avery</div>

          <div className="mt-2 font-mono text-7xl font-black text-[#238636]">
            {scores.Avery}
          </div>
        </div>

        <div className="text-2xl font-light text-[#8b949e]">VS</div>

        <div className="text-center">
          <div className="text-2xl font-bold text-[#f0f6fc]">Mitchell</div>

          <div className="mt-2 font-mono text-7xl font-black text-[#da5552]">
            {scores.Mitchell}
          </div>
        </div>
      </div>

      <div className="mb-10 grid w-full max-w-5xl grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3">
        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 text-center">
          <div className="text-md mb-3 font-bold tracking-wider text-[#58a6ff] uppercase">
            📅 First Date
          </div>

          <div className="text-sm font-semibold tracking-wide text-white">
            {firstDateWinner}
          </div>
        </div>

        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 text-center">
          <div className="text-md mb-3 font-bold tracking-wider text-[#58a6ff] uppercase">
            📅 Anniversary
          </div>

          <div className="text-sm font-semibold tracking-wide text-white">
            {anniversaryWinner}
          </div>
        </div>

        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 text-center">
          <div className="text-md mb-3 font-bold tracking-wider text-[#ecc94b] uppercase">
            🕛 Noon Games
          </div>

          <div className={`tracking-wide ${noonDisplay.activeStyle}`}>
            {noonDisplay.text}
          </div>
        </div>

        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 text-center">
          <div className="text-md mb-3 font-bold tracking-wider text-[#ff7b72] uppercase">
            🎮 WWF2™
          </div>

          <div className="text-sm font-semibold tracking-wide text-white">
            {wwf2Winner}
          </div>
        </div>

        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 text-center">
          <div className="text-md mb-3 font-bold tracking-wider text-[#79c0ff] uppercase">
            🔢 210
          </div>

          <div className="text-sm font-semibold tracking-wide text-white">
            {game210Winner}
          </div>
        </div>

        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 text-center">
          <div className="text-md mb-3 font-bold tracking-wider text-[#ecc94b] uppercase">
            🕒 3PM Games
          </div>

          <div className={`tracking-wide ${pm3Display.activeStyle}`}>
            {pm3Display.text}
          </div>
        </div>

        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 text-center">
          <div className="text-md mb-3 font-bold tracking-wider text-[#bc8cff] uppercase">
            🐸 Toad
          </div>

          <div className="text-sm font-semibold tracking-wide text-white">
            {toadWinner}
          </div>
        </div>

        <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 text-center">
          <div className="text-md mb-3 font-bold tracking-wider text-[#ecc94b] uppercase">
            🏪 7/11
          </div>

          <div className="text-sm font-semibold tracking-wide text-[#58a6ff]">
            {sevenElevenWinner}
          </div>
        </div>
      </div>

      <div className="text-md mb-10 flex w-full max-w-5xl justify-center gap-12 rounded-lg border border-[#da5552] bg-red-500/10 px-10 py-3 font-medium">
        <span className="font-bold text-[#ff7b72]">
          🚨 ANTSY PENALTY COUNTERS:
        </span>

        <span>
          Avery:{" "}
          <strong className="font-mono text-white">{penalties.Avery}</strong>
        </span>

        <span>
          Mitchell:{" "}
          <strong className="font-mono text-white">{penalties.Mitchell}</strong>
        </span>
      </div>

      <div className="w-full max-w-5xl rounded-xl border border-[#30363d] bg-[#161b22] p-6 shadow-md">
        <div className="mb-4 border-b border-[#30363d] pb-2 text-lg font-bold text-[#f0f6fc]">
          ⏱️ Real-Time Timeline Records
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[#21262d] text-xs text-[#8b949e] uppercase">
                <th className="px-2 py-3">Game Slot</th>

                <th className="px-2 py-3">Winner</th>

                <th className="px-2 py-3">Margin</th>

                <th className="px-2 py-3">Text</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-[#21262d]">
              {Object.entries(matches)
                .filter(([_, match]) => match.resolved === true)
                .map(([gameName, match]) => (
                  <tr
                    key={gameName}
                    className="transition-colors hover:bg-[#21262d]/30"
                  >
                    <td className="px-2 py-3 font-bold text-white uppercase">
                      {gameName.replaceAll("_", " ")}
                    </td>

                    <td className="px-2 py-3 font-semibold text-[#58a6ff]">
                      {match.winner ?? "Tie"}
                    </td>

                    <td className="px-2 py-3 font-mono text-sm font-bold text-[#58a6ff]">
                      {match.margin_ms != null ? `${match.margin_ms}ms` : "—"}
                    </td>

                    <td className="px-2 py-3 text-sm text-gray-400">
                      {match.winner_text ?? match.text ?? "—"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
