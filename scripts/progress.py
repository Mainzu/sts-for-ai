"""Progress of a long phase (self-play, solve step, cache build, training).

In a terminal, one line redrawn in place: a bar, count, rate and ETA. In a
log (stdout redirected), a line each time `every_s` seconds have passed or
another `every_frac` of the total is done, whichever comes first, and a
final line with the total time.

    p = Progress("self-play", len(specs), log)
    for chunk in chunks:
        ...
        p.update(len(chunk))
    p.close()
"""

import sys
import time

BAR = 24


def _dur(s):
    s = int(s)
    return f"{s // 3600}h{s // 60 % 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


class Progress:
    def __init__(self, label, total, log=print, every_s=30.0, every_frac=0.1, tty=None, clock=time.monotonic):
        self.label, self.total, self.log = label, max(0, int(total)), log or print
        self.every_s, self.every_frac, self.clock = every_s, every_frac, clock
        self.tty = sys.stdout.isatty() if tty is None else tty
        self.done = 0
        self.start = self.last_t = clock()
        self.last_frac = 0.0
        self.closed = False

    def _status(self, now):
        el = now - self.start
        rate = self.done / el if el > 0 else 0.0
        eta = (self.total - self.done) / rate if rate > 0 and self.total else None
        pct = 100.0 * self.done / self.total if self.total else 100.0
        tail = f"{rate:.1f}/s" + ("" if eta is None else f", ETA {_dur(eta)}")
        return pct, f"{self.done}/{self.total} ({pct:.0f}%), {_dur(el)}, {tail}"

    def update(self, n=1):
        self.done += n
        now = self.clock()
        if self.tty:
            if now - self.last_t < 0.2 and self.done < self.total:
                return  # redrawn at most 5 times a second
            self.last_t = now
            pct, s = self._status(now)
            fill = int(BAR * pct / 100)
            sys.stdout.write(f"\r  {self.label} [{'#' * fill}{'.' * (BAR - fill)}] {s}   ")
            sys.stdout.flush()
            return
        frac = self.done / self.total if self.total else 1.0
        if self.done < self.total and (now - self.last_t >= self.every_s or frac - self.last_frac >= self.every_frac):
            self.log(f"  {self.label}: {self._status(now)[1]}")
            self.last_t, self.last_frac = now, frac

    def close(self, final=True):
        """Ends the phase; `final` False skips the closing line (its caller
        logs its own, as training does per epoch)."""
        if self.closed:
            return
        self.closed = True
        el = self.clock() - self.start
        if self.tty:
            sys.stdout.write("\n" if final else "\r" + " " * (BAR + 60) + "\r")
            sys.stdout.flush()
        if final:
            self.log(f"  {self.label}: {self.done}/{self.total} done in {_dur(el)}")
