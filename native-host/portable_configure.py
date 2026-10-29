import sys
from pathlib import Path
from config_manager import settings, update_settings


def main(args):
    if args == ['--check-existing']:
        root = settings()['root']
        if not root:
            return 2  # Registration asks for a directory only on first use.
        if not Path(root).is_absolute() or not Path(root).is_dir():
            raise ValueError('已保存的根目录暂不可用，请连接相应磁盘或在插件设置中修改；原设置已保留')
        print('沿用已保存的根目录：'+root)
        return 0
    if len(args) != 1:
        raise ValueError('请选择保存根目录')
    cfg = update_settings({'root':args[0]})
    print('保存根目录：'+cfg['root'])
    return 0


if __name__ == '__main__':
    try:
        code = main(sys.argv[1:])
    except Exception as e:
        print(str(e),file=sys.stderr);code = 1
    raise SystemExit(code)
