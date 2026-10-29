import sys
from config_manager import update_settings
if __name__=='__main__':
    try:
        if len(sys.argv)!=2: raise ValueError('请选择保存根目录')
        cfg=update_settings({'root':sys.argv[1]})
        print('保存根目录：'+cfg['root'])
    except Exception as e:
        print(str(e),file=sys.stderr);raise SystemExit(1)
