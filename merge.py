import os
import subprocess
from toolkit.Common import format_id
import re


def merge_videos(video_files, output_file):
    ffmpeg_command = ['ffmpeg', '-f', 'concat', '-safe', '0']
    concat_txt = '\n'.join(['file {}'.format(video_file) for video_file in video_files])
    with open('tmp/concat.txt', 'w', encoding='utf-8') as f:
        f.write(concat_txt)
    ffmpeg_command.extend(['-i', 'tmp/concat.txt', '-c', 'copy', output_file, '-y'])
    print(ffmpeg_command)
    subprocess.run(ffmpeg_command)


def get_video_duration(video_file):
    # 使用ffmpeg获取视频时长
    result = subprocess.run(['ffmpeg', '-i', video_file], capture_output=True, text=True)
    output = result.stderr
    duration_match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d+)', output)
    if duration_match:
        hours, minutes, seconds, milliseconds = map(int, duration_match.groups())
        print(hours, minutes, seconds, milliseconds)
        total_mili_seconds = hours * 3600000 + minutes * 60000 + seconds * 1000 + milliseconds * 10
        return total_mili_seconds
    else:
        return None


def adjust_timestamps(subtitle_file, video_duration):
    import re

    with open(subtitle_file, 'r', encoding='utf-8') as f:
        lines = f.read()

    # 提取每个字幕的时间戳和内容
    subtitles = []
    pattern = r'(\d+)\n(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})\n(.+?)(?=\n\d+\n|$)'
    matches = re.finditer(pattern, lines, re.DOTALL)

    for match in matches:
        subtitle_index = int(match.group(1))
        start_time = int(match.group(2)) * 3600000 + int(match.group(3)) * 60000 + int(match.group(4)) * 1000 + int(
            match.group(5))
        end_time = int(match.group(6)) * 3600000 + int(match.group(7)) * 60000 + int(match.group(8)) * 1000 + int(
            match.group(9))
        content = match.group(10).strip()
        subtitles.append((subtitle_index, start_time, end_time, content))

    print(subtitles)

    # 根据视频持续时间调整时间戳
    for i, subtitle in enumerate(subtitles):
        start_time = subtitle[1]
        end_time = subtitle[2]
        start_time += video_duration
        end_time += video_duration
        subtitles[i] = (subtitle[0], start_time, end_time, subtitle[3])

    # 重新生成修正后的字幕内容
    adjusted_subtitles = []
    for subtitle in subtitles:
        adjusted_subtitles.append(str(subtitle[0]))
        adjusted_subtitles.append('{} --> {}'.format(
            '{:02d}:{:02d}:{:02d},{}'.format((subtitle[1] // 3600000) % 60, (subtitle[1] // 60000) % 60,
                                             (subtitle[1] // 1000) % 60, subtitle[1] % 1000),
            '{:02d}:{:02d}:{:02d},{}'.format((subtitle[2] // 3600000) % 60, (subtitle[2] // 60000) % 60,
                                             (subtitle[2] // 1000) % 60, subtitle[2] % 1000)
        ))
        adjusted_subtitles.append(subtitle[3])
        adjusted_subtitles.append('')

    # 返回修正后的字幕内容
    return adjusted_subtitles


def merge_subtitles(subtitle_files, video_files, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        current_subtitle_index = 1
        video_duration = 0
        for subtitle_file, video_file in zip(subtitle_files, video_files):
            print(subtitle_file)
            adjusted_subtitles = adjust_timestamps(subtitle_file, video_duration)
            video_duration += get_video_duration(video_file)
            if video_duration is None:
                print("无法获取视频持续时间。")
                return
            for line in adjusted_subtitles:
                if line.strip().isdigit():
                    line = str(current_subtitle_index)
                    current_subtitle_index += 1
                f.write(line + '\n')


# 每次合并10个视频
path = input('视频文件路径:').replace('\\', '/')
num = len(os.listdir(f'{path}/srt'))
merge_videos([f'{path}/video/{format_id(i, 4)}.mp4' for i in range(num)], f'{path}/output.mp4')
merge_subtitles([f'{path}/srt/{format_id(i, 4)}.srt' for i in range(num)],
                [f'{path}/video/{format_id(i, 4)}.mp4' for i in range(num)], f'{path}/output.srt')
