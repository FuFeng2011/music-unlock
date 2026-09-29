# Third-Party Notices

本项目的核心解密算法移植自以下开源项目。它们各自保留其版权与许可证；本项目以 AGPL-3.0-or-later 发布（见 LICENSE），与下列 GPL 系许可证兼容。

## davidxuang/MusicDecrypto

- 用途：酷狗新格式（.kgm / .kgma / .vpr）T2 / T3 加密算法的参考实现（`core.py` 中 `_t2_decrypt` / `_t3_decrypt` / `_md5_swapped` 及头部布局解析）
- 许可证：GNU Affero General Public License v3.0 (AGPL-3.0)
- 仓库：https://github.com/davidxuang/MusicDecrypto

## 0x77fe/AudioDecrypt

- 用途：酷狗旧版 .kgm（MaskV2PreDef 方案）解密算法及常量表的参考实现（`core.py` 中 `kgm_legacy_decrypt` 与 TABLE1 / TABLE2 / MASK_V2_PREDEF）
- 许可证：GNU General Public License v3.0 (GPL-3.0)
- 仓库：https://github.com/0x77fe/AudioDecrypt

## 网易云 NCM 文件结构（经典 ncmdump 布局）

- 用途：NCM 文件头布局、keybox 掩码构建与封面区解析的参照（`core.py` 中 `ncm_decrypt`）
- 该文件结构为多年公开流传的社区知识，最早的公开实现来自 unlock-music 项目及 ncmdump 系列工具；本次实现独立编写，未直接复制其代码。

## PyCryptodome

- 用途：运行时依赖，NCM 元数据与密钥的 AES-128-ECB 解密
- 许可证：BSD 2-Clause License 及 Public Domain（详见其项目）
- 仓库：https://github.com/Legrandin/pycryptodome
