#!/usr/bin/env python3
"""Generate tiny local media fixtures, without fetching any external metadata."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parent / 'data/media'
movie = root / 'movies/Christmas Movie (2020)/Christmas Movie (2020).mp4'
other = root / 'movies/Harry Potter Example (2021)/Harry Potter Example (2021).mp4'
episode = root / 'tv/Example Show/Season 01/Example Show - S01E01 - Christmas Episode.mp4'
for path in (movie, other, episode):
    path.parent.mkdir(parents=True, exist_ok=True)
if not movie.exists():
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=320x180:r=10:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(movie)], check=True)
for path in (other, episode):
    if not path.exists():
        shutil.copyfile(movie, path)
poster = movie.parent / 'poster.jpg'
if not poster.exists():
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=300x450', '-frames:v', '1', str(poster)], check=True)
(movie.parent / 'movie.nfo').write_text('<movie><title>Christmas Movie</title><year>2020</year><mpaa>G</mpaa></movie>\n')
(other.parent / 'movie.nfo').write_text('<movie><title>Harry Potter Example</title><year>2021</year><mpaa>R</mpaa></movie>\n')
(episode.parent.parent / 'tvshow.nfo').write_text('<tvshow><title>Example Show</title><mpaa>G</mpaa></tvshow>\n')
episode.with_suffix('.nfo').write_text('<episodedetails><title>Christmas Episode</title><showtitle>Example Show</showtitle><season>1</season><episode>1</episode><mpaa>G</mpaa></episodedetails>\n')
print('Verification media ready.')
