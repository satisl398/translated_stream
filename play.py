import os.path
import time

import pyglet
import re
from toolkit.Common import format_id
import subprocess


# 视频文件路径列表
path = input("视频文件路径:")
video_dir = path + '\\video'
subtitle_dir = path + '\\srt'


# 获取视频分辨率
def get_video_resolution(video_file):
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=s=x:p=0',
        video_file
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        resolution = result.stdout.strip()
        return resolution.split('x')
    else:
        print("Error occurred:", result.stderr)
        return None


# 创建主窗口
screen = pyglet.canvas.Display().get_screens()[0]
width, height = get_video_resolution(f'{video_dir}/{format_id(0, 4)}.mp4')
width = int(width) if int(width) <= 1920 else 1920
height = int(height) if int(height) <= 1080 else 1080
window = pyglet.window.Window(width=width, height=height, screen=screen)

# 初始化全局变量
is_fullscreen = False
current_video_index = 0
player = pyglet.media.Player()
subtitles = []
subtitle_text = ''
subtitle_color = [255, 255, 255, 255]
font_size = 20
distance = 50
subtitle_x = window.width // 2
subtitle_y = 10


# 注册主窗口的绘制函数
@window.event
def on_draw():
    window.clear()
    player.get_texture().blit(0, 0)
    lines = subtitle_text.strip('\n').split('\n')
    line_num = len(lines)
    if line_num == 2:
        pyglet.text.Label(lines[1],
                          font_size=font_size,
                          x=subtitle_x, y=subtitle_y,
                          anchor_x='center', anchor_y='bottom',
                          color=subtitle_color).draw()
        pyglet.text.Label(lines[0],
                          font_size=font_size,
                          x=subtitle_x, y=subtitle_y + distance,
                          anchor_x='center', anchor_y='bottom',
                          color=subtitle_color).draw()
    elif line_num == 1:
        pyglet.text.Label(lines[0],
                          font_size=font_size,
                          x=subtitle_x, y=subtitle_y,
                          anchor_x='center', anchor_y='bottom',
                          color=subtitle_color).draw()
    else:
        print('maybe some errors occur')


# 注册按键事件处理函数(c键改变颜色，上下键改变字体大小）
@window.event
def on_key_press(symbol, modifiers):
    global subtitle_color, font_size, subtitle_y, subtitle_x, is_fullscreen

    # 切换字幕颜色
    if symbol == pyglet.window.key.C:
        rgb = [i - 255 // 4 for i in subtitle_color[:-1]]
        for idx, i in enumerate(rgb):
            rgb[idx] = i if i >= 0 else i + 255
        rgb.append(255)
        subtitle_color = rgb
    elif symbol == pyglet.window.key.V:
        r = subtitle_color[0] - 255 // 4
        r = r if r >= 0 else r + 255
        subtitle_color[0] = r
    elif symbol == pyglet.window.key.B:
        g = subtitle_color[1] - 255 // 4
        g = g if g >= 0 else g + 255
        subtitle_color[1] = g
    elif symbol == pyglet.window.key.N:
        b = subtitle_color[2] - 255 // 4
        b = b if b >= 0 else b + 255
        subtitle_color[2] = b
    elif symbol == pyglet.window.key.M:
        a = subtitle_color[3] - 255 // 4
        a = a if a >= 0 else a + 255
        subtitle_color[3] = a
    # 改变字幕位置
    elif symbol == pyglet.window.key.W:
        subtitle_y += 10
    elif symbol == pyglet.window.key.S:
        subtitle_y -= 10
    elif symbol == pyglet.window.key.A:
        subtitle_x -= 10
    elif symbol == pyglet.window.key.D:
        subtitle_x += 10
    # 改变字幕大小
    elif symbol == pyglet.window.key.UP:
        font_size += 2
    elif symbol == pyglet.window.key.DOWN:
        font_size -= 2
        if font_size < 1:
            font_size = 1
    # 切换全屏状态
    elif symbol == pyglet.window.key.F:
        is_fullscreen = not is_fullscreen
        window.set_fullscreen(is_fullscreen)


# 将SRT时间格式转换为秒数
def convert_srt_time_to_seconds(time_str):
    hours, minutes, seconds_millis = time_str.split(':')
    seconds, millis = seconds_millis.split(',')
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000
    return total_seconds


# 解析SRT字幕文件
def parse_srt(subtitle_path):
    with open(subtitle_path, 'r', encoding='utf-8') as file:
        content = file.read()
    # 使用正则表达式匹配SRT字幕格式
    pattern = r'(\d+)\n(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)\n(.+?)(?=\n\d+\n|$)'
    subtitles = re.findall(pattern, content, re.DOTALL)
    parsed_subtitles = []
    for subtitle in subtitles:
        start_time = subtitle[1]
        end_time = subtitle[2]
        text = subtitle[3]
        parsed_subtitles.append({
            'start_time': convert_srt_time_to_seconds(start_time),
            'end_time': convert_srt_time_to_seconds(end_time),
            'text': text
        })
    return parsed_subtitles


# 播放下一个视频
def play_next_video():
    global current_video_index
    global player
    global subtitles

    print('------------------------')
    print('切换下一个视频')
    print('------------------------')
    print()

    while True:
        if os.path.exists(f'{video_dir}/{format_id(current_video_index, 4)}.mp4'):
            # 加载视频
            video = pyglet.media.load(f'{video_dir}/{format_id(current_video_index, 4)}.mp4')
            break
        else:
            print("等待视频爬取")
            time.sleep(1)

    player.queue(video)

    # 加载对应的字幕
    subtitles = parse_srt(f'{subtitle_dir}/{format_id(current_video_index, 4)}.srt')

    # 播放视频
    player.play()

    # 更新视频索引
    current_video_index += 1


# 注册视频播放完成事件回调函数
player.push_handlers(on_eos=play_next_video)


# 更新字幕内容
def update_subtitle(dt):
    global subtitle_text

    # 获取当前视频时间
    current_time = player.time

    # 查找当前时间对应的字幕，如果和上一时字幕不同则更新
    for subtitle in subtitles:
        start_time = subtitle['start_time']
        end_time = subtitle['end_time']
        if start_time <= current_time <= end_time:
            if subtitle_text != subtitle['text']:
                subtitle_text = subtitle['text']
                print(subtitle['start_time'], subtitle['end_time'])
                print(subtitle['text'])
                print()
            break
    else:
        # 如果没有找到匹配的字幕，则显示空文本
        subtitle_text = ''


# 启动定时器以便每秒检查是否需要更新字幕
pyglet.clock.schedule_interval(update_subtitle, 1.0)

# 播放第一个视频
play_next_video()

# 启动事件循环
pyglet.app.run()
