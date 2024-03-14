#!/usr/bin/env python3

from pytube import YouTube
from moviepy.editor import VideoFileClip
from pathlib import Path
from argparse import ArgumentParser
import time
import ffmpeg
import json

DOWNLOAD_DIR = "downloads"

parser = ArgumentParser()
parser.add_argument('url', help="url for the video to be downloaded")
parser.add_argument('-s', '--start', type=int, default=0,
                    help="Start time for the subclip (can be number of seconds or timestamp)")
parser.add_argument('-e', '--end', type=int, default=0,
                    help="End time for the subclip (can be number of seconds or timestamp)")
parser.add_argument('-a', '--audio_only', action="store_true")
parser.add_argument('-v', '--video_only', action="store_true")
parser.add_argument('--overwrite', action="store_true", help="overwrite file if it exists already? (Default: False)")


class DownloadYoutube(YouTube):
  def __init__(self, url, **kwargs):
    super().__init__(url)
    self.url = url
    self.args = kwargs
    self.titlename = self._clean_titlename()
    self.audio_filename = f"{self.titlename}.wav"
    self.video_filename = f"{self.titlename}.mp4"
    self.json_filename  = f"{self.titlename}.json"
    self.outputfile = self._outputs_dir(DOWNLOAD_DIR) / self.video_filename
    self.outputjson = self._outputs_dir(DOWNLOAD_DIR) / self.json_filename

  def download(self):
    def get_audio_track():
      return self.streams \
        .filter(only_audio=True, file_extension="mp4") \
        .order_by('abr') \
        .desc() \
        .first() \
        .download(output_path=self.tempdir, filename=self.audio_filename)

    def get_video_track():
      return self.streams \
        .filter(adaptive=True, file_extension="mp4") \
        .order_by('resolution') \
        .desc() \
        .first() \
        .download(output_path=self.tempdir, filename=self.video_filename)

    def stitch_audio_video():
      overwrite = '-y' if self.args.get("overwrite") else '-n'
      try:
        ffmpeg.concat(
          ffmpeg.input(self.tempdir / self.video_filename), 
          ffmpeg.input(self.tempdir / self.audio_filename), 
          a=1, 
          v=1
          ).output(str(self.outputfile), loglevel="fatal").global_args(overwrite).run()
      except ffmpeg._run.Error as e:
        pass

    def clear_temp_dir():
      for _file in self.tempdir.glob("*"):
        if _file.is_file():
          _file.unlink()
      self.tempdir.rmdir()

    def save_metadata():
      metadata = {
        "name": self.outputfile.name,
        "url": self.url,
        "channel_url": self.channel_url,
        "length": self._get_time_from_s(self.length),
        "download_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "download_time_took": self._get_time_from_s(self.dl_end - self.dl_start),
        "file_size": f"{self.outputfile.stat().st_size >> 20}MB",
        "args": self.args
        }
      with open(self.outputjson, "w") as outputfile:
        json.dump(metadata, outputfile)

    def move_output_file(filename):
      _filename = Path(filename)
      return _filename.rename(self._outputs_dir(DOWNLOAD_DIR) / _filename.name)

    if self.outputfile.is_file() and not self.args.get('overwrite'):
      exit("output file exists. if you really want to download, run with the --overwrite option.")
    self.dl_start = time.time()
    self.tempdir = self._outputs_dir("temp")
    if self.args['audio_only']:
      self.outputfile = move_output_file(get_audio_track())
    elif self.args['video_only']:
      move_output_file(get_video_track())
    else:
      get_audio_track()
      get_video_track()
      stitch_audio_video()
    clear_temp_dir()
    self.dl_end = time.time()
    save_metadata()

  def _get_time_from_s(self, sec):
    return time.strftime('%H:%M:%S', time.gmtime(sec))

  def _outputs_dir(self, _dir):
    download_path = Path().cwd() / _dir
    if not download_path.is_dir():
      download_path.mkdir()
    return download_path

  def _clean_titlename(self):
    return self.title.replace("/", "-")


class Subclip():
  def __init__(self, filename, start, end):
    self.filename = Path(filename)
    self.start, self.end = start, end
    self.outputfile = self.filename.parent / f"{self.filename.stem}-subclip-{start}-{end}{self.filename.suffix}"

  def clip_file(self):
    _filename = str(self.filename)
    _outputfile = str(self.outputfile)
    with VideoFileClip(_filename) as clip_file:
      clip_file.subclip(self.start, self.end).write_videofile(_outputfile, codec="libx264")


if __name__ == '__main__':
  kwargs = parser.parse_args()
  yt = DownloadYoutube(**vars(kwargs))
  yt.download()