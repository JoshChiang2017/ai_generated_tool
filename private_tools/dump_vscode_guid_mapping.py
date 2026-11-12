"""
VS Code 工作區 GUID 對照工具

用途：
    掃描 VS Code 的 workspaceStorage 目錄，讀取各子目錄中的 workspace.json，並列出儲存資料夾名稱（GUID）
    與實際工作區路徑的對應關係。
    可辨識單一資料夾工作區、workspace 檔案及多根工作區，也會列出缺少設定檔、欄位不明或讀取失敗的項目和統計資訊。

使用方式：
    python vscode_guid_mapping.py

    執行後工具只讀取並列印資料，不會修改workspaceStorage 中的檔案。

需求：
    僅使用 Python 標準函式庫，無需安裝額外套件。
"""

import os
import json
from pathlib import Path
from urllib.parse import unquote

def map_workspace_folders(workspace_storage_path):
    """
    掃描 VS Code workspaceStorage 資料夾，映射 GUID 與資料夾路徑
    
    Args:
        workspace_storage_path: workspaceStorage 的路徑
    """
    workspace_storage = Path(workspace_storage_path)
    
    if not workspace_storage.exists():
        print(f"❌ 路徑不存在: {workspace_storage_path}")
        return
    
    print(f"📂 掃描路徑: {workspace_storage_path}\n")
    
    # 收集所有結果
    valid_workspaces = []  # (guid, type, path)
    no_json_items = []
    no_field_items = []
    error_items = []
    total_dirs = 0
    
    # 遍歷所有子資料夾
    for item in workspace_storage.iterdir():
        if item.is_dir():
            total_dirs += 1
            workspace_json = item / "workspace.json"
            
            # 檢查是否存在 workspace.json
            if not workspace_json.exists():
                no_json_items.append(item.name)
                continue
            
            try:
                with open(workspace_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 提取 folder 欄位（單一資料夾工作區）
                if 'folder' in data:
                    folder_uri = data['folder']
                    folder_path = folder_uri.replace('file:///', '')
                    folder_path = unquote(folder_path)
                    valid_workspaces.append((item.name, '📁 folder', folder_path))
                
                # 處理 workspace 欄位（遠程或本地 .code-workspace 文件）
                elif 'workspace' in data:
                    workspace_uri = data['workspace']
                    workspace_path = unquote(workspace_uri)
                    
                    # 移除 file:/// 前綴（如果是本地路徑）
                    if not workspace_uri.startswith('vscode-remote://'):
                        workspace_path = workspace_path.replace('file:///', '')
                    
                    valid_workspaces.append((item.name, '📚 workspace', workspace_path))
                
                # 處理多根工作區（configuration 欄位）
                elif 'configuration' in data:
                    config_uri = data['configuration']
                    config_path = config_uri.replace('file:///', '')
                    config_path = unquote(config_path)
                    valid_workspaces.append((item.name, '📚 多根工作區', config_path))
                
                # JSON 存在但沒有任何已知欄位
                else:
                    no_field_items.append(item.name)
                
            except json.JSONDecodeError:
                error_items.append((item.name, "JSON 解析錯誤"))
            except Exception as e:
                error_items.append((item.name, str(e)))
    
    # ========== 分類工作區 ==========
    folder_workspaces = [(g, t, p) for g, t, p in valid_workspaces if 'folder' in t]
    workspace_workspaces = [(g, t, p) for g, t, p in valid_workspaces if 'workspace' in t]
    config_workspaces = [(g, t, p) for g, t, p in valid_workspaces if '多根' in t]
    
    # ========== 顯示 folder 工作區 ==========
    if folder_workspaces:
        print("=" * 130)
        print(f"{'📁 folder 工作區':^130}")
        print("=" * 130)
        print(f"{'GUID':<32} | {'類型':<12} | {'資料夾路徑'}")
        print("=" * 130)
        
        for guid, wtype, path in folder_workspaces:
            print(f"{guid:<32} | {wtype:<12} | {path}")
        
        print("=" * 130)
        print(f"共 {len(folder_workspaces)} 個\n")
    
    # ========== 顯示 workspace 工作區 ==========
    if workspace_workspaces:
        print("=" * 130)
        print(f"{'📚 workspace 工作區':^130}")
        print("=" * 130)
        print(f"{'GUID':<32} | {'類型':<12} | {'資料夾路徑'}")
        print("=" * 130)
        
        for guid, wtype, path in workspace_workspaces:
            print(f"{guid:<32} | {wtype:<12} | {path}")
        
        print("=" * 130)
        print(f"共 {len(workspace_workspaces)} 個\n")
    
    # ========== 顯示 configuration 工作區 ==========
    if config_workspaces:
        print("=" * 130)
        print(f"{'📚 多根工作區 (configuration)':^130}")
        print("=" * 130)
        print(f"{'GUID':<32} | {'類型':<12} | {'資料夾路徑'}")
        print("=" * 130)
        
        for guid, wtype, path in config_workspaces:
            print(f"{guid:<32} | {wtype:<12} | {path}")
        
        print("=" * 130)
        print(f"共 {len(config_workspaces)} 個\n")
    
    # ========== 顯示問題項目 ==========
    problem_count = len(no_json_items) + len(no_field_items) + len(error_items)
    
    if problem_count > 0:
        print("=" * 130)
        print(f"{'⚠️ 無法識別的項目':^130}")
        print("=" * 130)
        print(f"{'GUID':<32} | {'問題描述'}")
        print("=" * 130)
        
        for guid in no_json_items:
            print(f"{guid:<32} | 沒有 workspace.json")
        
        for guid in no_field_items:
            print(f"{guid:<32} | JSON 中無 folder、workspace 或 configuration 欄位")
        
        for guid, error_msg in error_items:
            print(f"{guid:<32} | 錯誤: {error_msg}")
        
        print("=" * 130)
        print(f"共 {problem_count} 個無法識別的項目\n")
    
    # ========== 統計資訊 ==========
    print("="* 130)
    print(f"📊 統計資訊:")
    print(f"   總資料夾數: {total_dirs}")
    print(f"   ✅ folder 工作區: {len(folder_workspaces)}")
    print(f"   ✅ workspace 工作區: {len(workspace_workspaces)}")
    print(f"   ✅ configuration 多根工作區: {len(config_workspaces)}")
    print(f"   ⚠️  無 workspace.json: {len(no_json_items)}")
    print(f"   ⚠️  無已知欄位: {len(no_field_items)}")
    print(f"   ❌ 錯誤: {len(error_items)}")
    print("="* 130)


if __name__ == "__main__":
    # 預設的 workspaceStorage 路徑
    default_path = os.path.expandvars(r"C:\Users\josh.chiang\AppData\Roaming\Code\User\workspaceStorage")
    
    # 你也可以使用環境變數動態取得使用者名稱
    # default_path = os.path.expandvars(r"%APPDATA%\Code\User\workspaceStorage")
    
    print("🔍 VS Code 工作區映射工具\n")
    
    # 讓使用者選擇使用預設路徑或輸入自訂路徑
    use_default = input(f"使用預設路徑? ({default_path})\n按 Enter 使用預設，或輸入自訂路徑: ").strip()
    
    if use_default:
        target_path = use_default
    else:
        target_path = default_path
    
    print()
    map_workspace_folders(target_path)
    
    input("\n按 Enter 鍵結束...")
