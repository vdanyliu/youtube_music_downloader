import curses
import threading
import time
from contextlib import contextmanager


class Bar:
    def __init__(self, total_amount: int):
        self.total_amount = total_amount
        self.actual_amount = 0

    @property
    def get_percent(self) -> float:
        return float("{:.2f}".format(self.actual_amount / self.total_amount * 100))

    def increase(self, amount=1):
        self.actual_amount += amount


class BarsHub:
    def __init__(self, refresh_rate: float = 1):
        self.bars: dict[str, Bar] = dict()
        self.daemon_run = False
        self._refresh_rate = refresh_rate

    @contextmanager
    def create_bar(self, name: str, total_amount: int) -> Bar:
        self._init_new_bar(name=name, total_amount=total_amount)
        yield self.bars[name]
        self._del_bar(name)

    def _init_new_bar(self, name: str, total_amount: int):
        self.bars[name] = Bar(total_amount)
        if not self.daemon_run:
            self._run_daemon()
        return self.bars[name]

    def _del_bar(self, name: str):
        self.bars.pop(name)
        if not self.bars:
            self.daemon_run = False

    def _run_daemon(self):
        self.daemon_run = True
        threading.Thread(target=self._run_ncurses_process, daemon=True).start()

    def _run_ncurses_process(self):
        bar: Bar
        try:
            stdscr = curses.initscr()
            while self.daemon_run:
                stdscr.clear()
                for i, (name, bar) in enumerate(self.bars.items()):
                    stdscr.addstr(i, 0, f"{name}: {bar.actual_amount}/{bar.total_amount} {bar.get_percent}%")
                stdscr.refresh()
                time.sleep(self._refresh_rate)
        finally:
            curses.endwin()
