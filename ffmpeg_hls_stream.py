# 自行添加百度api，腾讯api,安装ffmpeg，faster-whisper模型
# 百度api和腾讯api分别添加baidu_appid,baidu_appkey和tencent_appid,tencent_appkey在系统环境上
# faster whisper模型地址 https://huggingface.co/Systran

import subprocess
import time
import datetime
import shutil
from toolkit.Common import format_id, create_directory, load_private_parameters
import requests
from toolkit.Translator import baidu_api, tencent_api
from faster_whisper import WhisperModel
from zhconv import convert
import math
import os

url = input('请输入直播流:')
internal_time = 30  # 直播切片持续时间
wrap_num = 2  # 爬取总缓存切片数

from_lang = 'auto'  # 源语言
to_lang = 'zh'  # 目标翻译语言

max_silence_time = 2  # 最大静默时长，分段用
max_sentence_length = {
    'en': 120,
    'zh': 20
}  # 最大段落长度，分段用

(model_path,) = load_private_parameters('info', ('model_path',))  # 模型路径
device, compute_type = 'cuda', 'float16'
model = WhisperModel(model_path, device=device, compute_type=compute_type)  # 模型参数设置

create_directory(f'tmp')
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
outputs_path = f'outputs/{timestamp}'
create_directory(outputs_path)
create_directory(f'{outputs_path}/srt')
create_directory(f'{outputs_path}/video')


def get_stream():
    command = [
        'ffmpeg',
        '-i', url,
        '-f', 'segment',
        '-segment_time', str(internal_time),
        '-segment_wrap', str(wrap_num),
        '-c:v', 'libx264',
        '-c:a', 'aac',
        f'tmp/%01d-1.mp4', '-y'
    ]
    with open('tmp/stream.log', 'w') as f:
        process = subprocess.Popen(command, stderr=f)
    return process


def extract_audio(name, verbose=True):
    command = [
        'ffmpeg',
        '-i', f'{name}.mp4',
        '-vn',
        '-c:a', 'libmp3lame',
        '-ar', '16000',
        f'{name}.mp3', '-y'
    ]
    data = subprocess.run(command, capture_output=True, check=True)
    if not data.returncode and verbose:
        print('音频分离完成')


def transcribe(name, mode=1, verbose=True):
    segments, info = model.transcribe(f'{name}.mp3', language=None, word_timestamps=True,
                                      condition_on_previous_text=False, vad_filter=True)
    language = info.language

    # 翻译结果分段方法
    if mode == 1:
        sentences = segments2sentences_1(segments, language, verbose)
    else:
        sentences = segments2sentences_2(segments, verbose)

    if verbose:
        print(language)
        print('转录完成')

    return sentences, language


# 尽可能的把句子凑成一块，使语义相对完整，便于翻译
def segments2sentences_1(segments, language, verbose):
    sentences = []
    sentence = None
    end = None
    for segment in segments:
        if verbose:
            print('-----------------')
            print(f'{segment.words[0].start}-->{segment.words[-1].end}')
            print(segment.text)
            print('-----------------')

        for idx, word in enumerate(segment.words):

            # 检验是否为段落开头，如果是则初始化sentence
            if sentence is None:
                sentence = {'text': '', 'start': word.start, 'end': word.end}

            # 检测段落是否过长，如果是则将该segment所有字符提交，并跳过本次循环
            if len(sentence['text']) > max_sentence_length.get(language, 120):
                for k in segment.words[idx:]:
                    sentence['text'] += convert(k.word, 'zh-cn')
                sentence.update({'end': segment.words[-1].end})
                sentences.append(sentence)

                if verbose:
                    print('段落过长，分段')
                    print(sentence)

                sentence = None
                break

            # # 检测当前字符结尾与下个字符开头相差时间是否过长，如果过长则提交段落
            # elif idx + 2 < len(segment.words) and segment.words[idx + 1].start - word.end > max_silence_time:
            #     sentence['text'] += convert(word.word, 'zh-cn')
            #     sentence.update({'end': word.end})
            #     sentences.append(sentence)
            #
            #     print('静默时间过长，分段')
            #     print(sentence)
            #
            #     sentence = None

            # 检验是否为段落结尾，如果是则提交段落
            elif word.word[-1] in ".。!！?？":
                sentence['text'] += convert(word.word, 'zh-cn')
                sentence.update({'end': word.end})
                sentences.append(sentence)

                if verbose:
                    print('段落结尾，分段')
                    print(sentence)

                sentence = None
            # 将字符添加至段落
            else:
                sentence['text'] += convert(word.word, 'zh-cn')
                end = word.end

    # 检验最后一段是否标点结尾并提交
    if sentence is not None:
        sentence.update({'end': end})
        sentences.append(sentence)

        if verbose:
            print('视频切片最后一段，分段')
            print(sentence)
    return sentences


# 尽可能的分段，使字幕实时性增加
def segments2sentences_2(segments, verbose):
    sentences = []
    for segment in segments:
        if verbose:
            print('-----------------')
            print(segment.words[0].start, segment.words[-1].end)
            print(segment.text)

        sentence = None
        for word in segment.words:
            # 检验是否为段落开头，如果是则初始化sentence
            if sentence is None:
                sentence = {'text': '', 'start': word.start, 'end': word.end}

            sentence['text'] += convert(word.word, 'zh-cn')

            # 检验是否为段落结尾，如果是则提交段落
            if word.word[-1] in ".。!！?？":
                sentence.update({'end': word.end})
                sentences.append(sentence)

                if verbose:
                    print('段落结尾，分段')
                    print(sentence)

                sentence = None

        # 检验最后一段是否标点结尾并提交
        if sentence is not None:
            sentence.update({'end': segment.words[-1].end})
            sentences.append(sentence)

            if verbose:
                print('segment最后一段，分段')
                print(sentence)
    return sentences


def translate(sentences, mode, verbose=True):
    try:
        results = []
        if mode == 'baidu':
            results = baidu_api(sentences, from_lang, to_lang)
        elif mode == 'tencent':
            results = tencent_api(sentences, from_lang, to_lang)
        if len(results) == 0:
            print('some errors may occur')
        if verbose:
            for r in results:
                print(f"{r['start']}-->{r['end']}")
                print(r['text'])
            print('翻译完成')
        return results
    except (requests.HTTPError,
            ConnectionResetError,
            requests.exceptions.ConnectionError) as msg:
        print('---------------------')
        print(msg)
        print('---------------------')
        time.sleep(5)
        return translate(sentences, mode, verbose)


def sentences2srt(name, sentences, verbose=True):
    with open(f'{name}.srt', 'w', encoding='utf-8') as f:
        for idx, sentence in enumerate(sentences):
            sentence_timestamp = []
            for j in (sentence['start'], sentence['end']):
                m, s = divmod(j, 60)
                h, m = divmod(m, 60)
                ms, s = math.modf(s)
                sentence_timestamp.append((int(h), int(m), int(s), int(ms * 1000)))
            f.write(f'{idx}\n')
            f.write(
                '{:0>2d}:{:0>2d}:{:0>2d},{:0>3d} --> {:0>2d}:{:0>2d}:{:0>2d},{:0>3d}\n'.format(sentence_timestamp[0][0],
                                                                                               sentence_timestamp[0][1],
                                                                                               sentence_timestamp[0][2],
                                                                                               sentence_timestamp[0][3],
                                                                                               sentence_timestamp[1][0],
                                                                                               sentence_timestamp[1][1],
                                                                                               sentence_timestamp[1][2],
                                                                                               sentence_timestamp[1][3]
                                                                                               ))
            f.write('{}\n\n'.format(sentence['text']))

    if verbose:
        print('字幕文件生成')


def srt_added_to_video(name, cnt, verbose=True):
    srt_path1 = f'{name}.srt'
    srt_path2 = f'{outputs_path}/srt/{cnt}.srt'
    video_path1 = f'{name}.mp4'
    video_path2 = f'{outputs_path}/video/{cnt}.mp4'
    with open(srt_path1, mode='r', encoding='utf-8') as f:
        num = len(f.read().strip())
    if num > 0:
        command = [
            'ffmpeg',
            '-i', video_path1,
            '-i', srt_path1,
            '-c:a', 'copy',
            '-c:v', 'copy',
            '-c:s', 'mov_text',
            video_path2
        ]
        data = subprocess.run(command, capture_output=True, check=True)
        if not data.returncode and verbose:
            print("字幕添加至视频成功")
        shutil.copy(srt_path1, srt_path2)
    else:
        shutil.copy(video_path1, video_path2)
        shutil.copy(srt_path1, srt_path2)


def main(cnt, tmp_id):
    output_name = f"tmp/{tmp_id}"
    shutil.copy(f'{output_name}-1.mp4', f'{output_name}.mp4')
    extract_audio(output_name, verbose=False)
    sentences, language = transcribe(output_name, mode=2, verbose=False)
    if language != 'zh' and len(sentences) > 0:
        sentences = translate(sentences, mode='tencent', verbose=True)
    sentences2srt(output_name, sentences, verbose=False)
    srt_added_to_video(output_name, cnt, verbose=False)


if __name__ == "__main__":
    pre_time = [0, 0]
    p = get_stream()
    time.sleep(internal_time * 0.1)
    try:
        cnt = 0
        while True:
            file_path = f'tmp/{cnt % wrap_num}-1.mp4'
            print(file_path)

            # 确定视频文件是否爬取完毕
            while True:
                time.sleep(internal_time * 0.2)

                data = subprocess.run(f'ffprobe {file_path}', capture_output=True)

                if not data.returncode:
                    print('ffmpeg爬取分段结束')
                    break
                else:
                    print('等待ffmpeg爬取分段')

            # 确认视频文件是否为新文件
            mtime = os.path.getmtime(file_path)
            print(datetime.datetime.fromtimestamp(mtime))

            if mtime == pre_time[cnt % wrap_num]:
                break
            pre_time[cnt % wrap_num] = mtime

            t = time.perf_counter()
            # 处理新视频切片
            main(format_id(cnt, 4), cnt % wrap_num)
            print(time.perf_counter() - t)

            cnt += 1
    finally:
        p.terminate()
