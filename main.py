import asyncio
import concurrent.futures
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import IO

import aiohttp
from pytube import YouTube

tread_pool = concurrent.futures.ThreadPoolExecutor()
tmp_dir = Path("./tmp")
tmp_dir.mkdir(exist_ok=True)
LOGGER = logging.getLogger(__name__)


async def convert_video_to_mp3(source: IO, target: str) -> str:
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


async def get_music_from_url(session: aiohttp.ClientSession, url: str) -> str:
    loop = asyncio.get_event_loop()
    youtube_video = await loop.run_in_executor(tread_pool, YouTube, url)
    title = youtube_video.title
    title = title.replace("\"", "").replace("'", "").replace("/", "")
    author = youtube_video.author
    audio_url = youtube_video.streams.filter(only_audio=True).last().url
    with tempfile.TemporaryFile(dir=tmp_dir) as tmp_fd:
        ii = 0
        async with session.get(audio_url) as r:
            i = 0
            while data := await r.content.read(2048):
                tmp_fd.write(data)
                i += len(data)
                if i > ii * 100_000:
                    print(f"{i}/{r.content_length}-{title}")
                    ii += 1
            tmp_fd.seek(0)
        return await convert_video_to_mp3(tmp_fd, Path(tmp_dir, f"{author}-{title}.mp3"))


async def amain():
    try:
        subprocess.run(["ffmpeg", "-version"])
    except Exception as ex:
        LOGGER.exception(ex)
        LOGGER.warning("You have to install \"ffmpeg\"")
        return
    source_path = Path("./url_list.txt")
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

    async with aiohttp.ClientSession(raise_for_status=True, timeout=aiohttp.ClientTimeout(total=10 * 60)) as session:
        with open(source_path) as url_list_fd:
            urls = [line.rstrip() for line in url_list_fd if "http" in line]
        print(urls)
        tasks = []
        for url in urls:
            tasks.append(asyncio.create_task(get_music_from_url(session, url)))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(results)


if __name__ == '__main__':
    asyncio.run(amain())
