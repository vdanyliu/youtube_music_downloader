import asyncio
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import IO

import aiohttp
from aiohttp import ClientSession
from pytube import YouTube
from unidecode import unidecode

tmp_dir = Path("./tmp")
source_path = Path("./url_list.txt")
tmp_dir.mkdir(exist_ok=True)
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler(sys.stdout))


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"])
    except Exception as ex:
        LOGGER.exception(ex)
        LOGGER.warning("ffmpeg required")
        exit(0)


def get_source_list() -> IO:
    if not source_path.exists():
        with open(source_path, "w+") as fd:
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

    with source_path.open() as fd:
        urls = [line.strip() for line in fd if "http" in line]
        LOGGER.info(urls)
        return urls


async def download_file(session: ClientSession, url: str, file: IO, tag: str) -> None:
    ii = 0
    async with session.get(url) as r:
        i = 0
        while data := await r.content.read(1024):
            file.write(data)
            i += len(data)
            if i > ii * 100_000:
                LOGGER.info(f"{i}/{r.content_length}-{tag}")
                ii += 1
        file.seek(0)


async def convert_file_to_mp3(source: IO, target: str) -> str:
    cmd = [
        "ffmpeg",
        f"-i -" if sys.platform == 'win32' else f"-i /dev/stdin",
        f"-vn -ac 2 -b:a 192k \"{str(target)}\" -n",
    ]
    proc = await asyncio.create_subprocess_shell(
        cmd=" ".join(cmd),
        stdin=source.fileno(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if stdout:
        print(f'[stdout]\n{stdout.decode()}')
    if stderr:
        print(f'[stderr]\n{stderr.decode()}')
    return target


async def get_music_form_url(session: aiohttp.ClientSession, url: str) -> str:
    y_object = YouTube(url)
    title, author = unidecode(y_object.title), unidecode(y_object.author)
    stram_url = y_object.streams.filter(only_audio=True).last().url
    with tempfile.TemporaryFile(dir=tmp_dir) as tmp_fd:
        await download_file(session, stram_url, tmp_fd, f"{title}")
        return await convert_file_to_mp3(tmp_fd, Path(tmp_dir, f"{author}-{title}.mp3"))


async def amain():
    check_ffmpeg()
    urls = get_source_list()
    session = aiohttp.ClientSession(raise_for_status=True)
    tasks = []
    for url in urls:
        tasks.append(get_music_form_url(session, url))
        await asyncio.sleep(0)
    LOGGER.info(await asyncio.gather(*tasks, return_exceptions=True))
    await session.close()


if __name__ == '__main__':
    LOGGER.setLevel(logging.DEBUG)
    asyncio.run(amain())
