r"""Run from Windows: py -3 tests\windows_integration.py [--submit]. Never submits by default."""
import sys, os, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'native-host'))
from bitcomet import check_bitcomet, launch
from config_manager import settings
if os.name!='nt': raise SystemExit('仅支持 Windows：待真机验证')
print(json.dumps(check_bitcomet(settings()),ensure_ascii=False,indent=2))
if '--submit' in sys.argv:
    print('此测试将真实请求打开一条你有权下载的磁力链接。')
    uri=input('粘贴测试磁力链接（留空取消）：').strip()
    if uri and input('输入 SEND 明确确认提交：')=='SEND':print(launch(uri,settings()))
else: print('只进行了检测，没有提交磁力任务。检查扩展设置显示“已连接”，再打开示例/目标帖子执行完整手工测试。')
