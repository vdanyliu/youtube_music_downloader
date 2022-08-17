import asyncio
import functools
import logging
import os
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from itertools import count
from pathlib import Path
from urllib.parse import urlparse

import youtube_dl

# logging.basicConfig(level=logging.INFO)
from custom_progress_bar import cpb_bars

LOGGER = logging.getLogger(__name__)


class UrlsSourceParser:
    def __init__(self, source_path=os.path.join(os.curdir, "url_list.txt")):
        self.source_path = source_path

    def parse(self):
        try:
            with open(self.source_path, "r") as fd:
                return [line.strip() for line in fd if "http" in line]
        except FileNotFoundError:
            self._first_launch()

    def _first_launch(self):
        with open(self.source_path, "w+") as fd:
            fd.write(
                '''
                Welcome to 'some_service'
                just put in this file youtube url, separate by newline
                    example:
                        https://www.youtube.com/watch?v=lwZDVGxJjCw&list=RDCMUCVHOlMtc4e0rrQlJvjjnRmg&start_radio=1
                        https://music.youtube.com/watch?v=1mBx7w32jRw&list=RDTMAK5uy_n_5IN6hzAOwdCnM8D8rzrs3vDl12UcZpA
                        https://music.youtube.com/watch?v=bDNuAdjhgmk&list=RDTMAK5uy_n_5IN6hzAOwdCnM8D8rzrs3vDl12UcZpA

                p.s. You should have ffmpeg
                ''')
        exit(0)


class YouTubeDownloader:
    chunk_size = 1
    tmp_dir = Path('tmp').resolve()

    def __init__(self, executor=None):
        self.executor = executor
        self.counter = count(1)
        self._init_tmp_dirs()

    async def adownload_video(self, url: str) -> tuple[Path, str]:
        loop = asyncio.get_event_loop()
        video_path, video_title = await loop.run_in_executor(
            executor=self.executor, func=functools.partial(self.download_video, url))
        return video_path, video_title

    def download_video(self, url: str) -> tuple[Path, str]:
        with youtube_dl.YoutubeDL({'format': 'bestaudio/best'}) as ydl:
            video_info = ydl.extract_info(url=url, download=False, process=False)
            video_id, video_title = video_info.get('id'), video_info.get('title')
            url = self.__get_best_audio_url(video_info)
            req = urllib.request.Request(url)

            r = urllib.request.urlopen(req)
            r_content_len = int(r.getheader("Content-Length"))
            tmp_video_path = Path(self.tmp_dir, video_id)
            with open(tmp_video_path, "wb+") as fd:
                with cpb_bars.create_bar(name=video_id, total_amount=r_content_len, ) as bar:
                    for _ in range(r_content_len):
                        data = r.read(self.chunk_size)
                        fd.write(data)
                        bar.increase(amount=self.chunk_size)
            if r.read(1):
                raise ValueError

            return tmp_video_path, video_title

    @staticmethod
    def __get_best_audio_url(video_info: dict) -> str:
        selected = None
        for v_format in video_info.get('formats'):
            if not selected:
                selected = v_format
            else:
                if v_format.get('abr', 0) > selected.get('abr', 0):
                    selected = v_format
        return selected.get('url')

    def _init_tmp_dirs(self):
        self.tmp_dir.mkdir(parents=True, exist_ok=True)


class VideoMusicConverter:
    async def convert_video_to_mp3(self, source: str, target: str) -> str:
        cmd = f"ffmpeg -i \"{source}\" -vn -ac 2 -b:a 192k \"{target}.mp3\" -n"
        LOGGER.warning(cmd)
        await self._run(cmd)
        return target

    @staticmethod
    async def _run(cmd):
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await proc.communicate()

        print(f'[{cmd!r} exited with {proc.returncode}]')
        if stdout:
            print(f'[stdout]\n{stdout.decode()}')
        if stderr:
            print(f'[stderr]\n{stderr.decode()}')


class YouTubeMusicService:
    youtube_link_template = "https://www.youtube.com/watch?v={}"

    def __init__(self, downloader: YouTubeDownloader, converter: VideoMusicConverter, parser: UrlsSourceParser):
        self.downloader = downloader
        self.converter = converter
        self.parser = parser

    async def run_pipeline(self, url: str) -> str:
        path_obj = urlparse(url)
        video_id_with_trash, *trash = path_obj.query.split("&")
        *trash, video_id = video_id_with_trash.split("=")
        video_path, video_title = await self.downloader.adownload_video(self.youtube_link_template.format(video_id))
        result = await self.converter.convert_video_to_mp3(str(video_path), str(Path(self.downloader.tmp_dir, video_title)))
        os.remove(str(video_path))
        return result

    def get_urls(self) -> list:
        urls = self.parser.parse()
        return urls


async def amain():
    try:
        subprocess.run(["ffmpeg", "-version"])
    except Exception as ex:
        LOGGER.exception(ex)
        LOGGER.warning("You have to install \"ffmpeg\"")
        exit(1)

    service = YouTubeMusicService(
        downloader=YouTubeDownloader(executor=ThreadPoolExecutor()),
        converter=VideoMusicConverter(),
        parser=UrlsSourceParser(),
    )
    tasks = [service.run_pipeline(url=url) for url in service.get_urls()]
    result = await asyncio.gather(*tasks, return_exceptions=False)
    await asyncio.sleep(1)
    LOGGER.warning("\n".join(["{} - {}".format(*values) for values in zip(service.get_urls(), result)]))


if __name__ == '__main__':
    asyncio.run(amain())
