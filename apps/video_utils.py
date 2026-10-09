import os
import re
import shutil
import subprocess
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

ALLOWED_EXTENSIONS = ('.mp4', '.mov', '.webm', '.m4v')
MAX_VIDEO_BYTES = 100 * 1024 * 1024
MAX_VIDEO_SECONDS = 120
TRANSCODE_TIMEOUT = 300

INSTAGRAM_HOSTS = {'instagram.com', 'www.instagram.com'}
YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}
INSTAGRAM_PATH = re.compile(r'^/(?:[A-Za-z0-9._]+/)?(?:p|reel|reels|tv)/[A-Za-z0-9_-]+/?$')

TRANSCODE_ARGS = [
    '-vf', "scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))'",
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '28', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
    '-c:a', 'aac', '-b:a', '96k',
    '-movflags', '+faststart',
]


def require_ffmpeg():
    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        raise ValidationError(_("Video processing is not available: ffmpeg is not installed on the server."))


def write_upload(fieldfile, directory):
    ext = os.path.splitext(fieldfile.name)[1].lower() or '.mp4'
    path = os.path.join(directory, 'source' + ext)
    with open(path, 'wb') as target:
        for chunk in fieldfile.chunks():
            target.write(chunk)
    return path


def _run(command):
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=TRANSCODE_TIMEOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        raise ValidationError(_("The video could not be processed. Upload a valid video file."))


def probe_duration(path):
    result = _run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', path])
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise ValidationError(_("The video could not be processed. Upload a valid video file."))


def validate_video_upload(fieldfile, directory):
    """Cheap checks first; returns the duration in seconds."""
    if os.path.splitext(fieldfile.name)[1].lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError(_("Unsupported video format. Allowed: MP4, MOV, WEBM, M4V."))
    if fieldfile.size > MAX_VIDEO_BYTES:
        raise ValidationError(_("The video is too large (maximum 100 MB)."))
    require_ffmpeg()
    duration = probe_duration(write_upload(fieldfile, directory))
    if duration > MAX_VIDEO_SECONDS:
        raise ValidationError(_("The video is too long (maximum 120 seconds)."))
    return duration


def transcode(source, target):
    _run(['ffmpeg', '-y', '-i', source, *TRANSCODE_ARGS, target])


def extract_poster(video_path, target, duration):
    _run(['ffmpeg', '-y', '-ss', str(min(1, duration / 2)), '-i', video_path, '-frames:v', '1', target])


def validate_video_url(url):
    """Accept only Instagram post/reel/tv links and YouTube links (exact hosts, http/https)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
    except ValueError:
        raise ValidationError(_("Enter a valid Instagram or YouTube link."))
    if parsed.scheme not in ('http', 'https') or not host:
        raise ValidationError(_("Enter a valid Instagram or YouTube link."))
    if host in INSTAGRAM_HOSTS:
        if not INSTAGRAM_PATH.match(parsed.path):
            raise ValidationError(_("Enter a link to a specific Instagram post or reel "
                                    "(for example https://www.instagram.com/reel/XXXX/)."))
    elif host in YOUTUBE_HOSTS:
        if parsed.path in ('', '/') and not parsed.query:
            raise ValidationError(_("Enter a link to a specific YouTube video."))
    else:
        raise ValidationError(_("Only Instagram and YouTube links are allowed."))
