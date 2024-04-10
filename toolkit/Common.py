import os


def create_directory(path):
    """
    创建文件夹
    :param path:目录相对路径
    """
    path = os.getcwd() + f"\\{path}"
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"新建{path}文件夹")
    else:
        print(f"已有{path}文件夹")


def format_id(id: int, size: int):
    if size > 1:
        return format_id(id // 10, size - 1) + str(id % 10)
    else:
        return str(id)


def load_private_parameters(file_name, parameter_names):
    try:
        with open(f'{file_name}.txt', mode='r', encoding='utf-8') as f:
            info = {}
            for i in f:
                info1 = i.strip().split('=', 1)
                info.update({info1[0]: info1[1]})
            parameters = []
            for i in parameter_names:
                parameters.append(info[i])
                print(f'读取到参数{i},值为{info[i]}')
            return parameters
    except FileNotFoundError:
        parameters = []
        for i in parameter_names:
            j = input(f'请输入你的{i}:')
            parameters.append(j)
        with open('info.txt', mode='w', encoding='utf-8') as f:
            for i in range(len(parameter_names)):
                f.write(f'{parameter_names[i]}={parameters[i]}\n')
        return parameters
