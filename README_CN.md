# FRT Memory Vault — 已验证基准数据（公开版）

> 本仓库只发布**实测基准数据**，不含任何源代码。
> 所有数据来自独立验证的测试运行（SHA 固定产物 + 第三方复核判据）。

## FRT 项目一览

| 项目 | 仓库 |
|---|---|
| FRT-AI-Rein | https://github.com/januspater630/FRT-AI-Rein |
| FRT-Memory-Vault | https://github.com/januspater630/FRT-Memory-Vault |
| FRT-Everitas-AI | https://github.com/januspater630/FRT-Everitas-AI |
| FRT-CFNS | https://github.com/januspater630/FRT-CFNS |
| FRT-SafeFS-Release | https://github.com/januspater630/FRT-SafeFS-Release |
| FRT-Cosmic-Encryption | https://github.com/januspater630/FRT-Cosmic-Encryption |
| Factor-recursion-theory | https://github.com/januspater630/Factor-recursion-theory |
| Janus-Vault | https://github.com/januspater630/Janus-Vault |
| Janus-Vault-Apple | https://github.com/januspater630/Janus-Vault-Apple |
| JanusShieldHaven | https://github.com/januspater630/JanusShieldHaven |
| janus-file-security | https://github.com/januspater630/janus-file-security |

## 核心已验证指标

| 指标 | 数值 | 说明 |
|---|---|---|
| 压缩倍率区间 | **3×–11×** | 实测，非估算 |
| 字符级恢复 | **≥99%** | 无损恢复已验证 |
| 高倍率边界测试点 | **11.93×** | 保持无损展开能力 |
| 单次真实测试语料 | **345 MB** | `_core_0804_0818.txt` |
| 处理的记忆/语义段 | **93,544** | |
| 覆盖的唯一句级信息 | **979,069** | |

## 为什么这不是「删除式压缩」

删除路线在约 **2.9×** 附近开始损失 ≥99% 字符保真度（实测：2.92× 时 95.59%）。
结构化「存在/访问路径解耦」路线在 **11.93×** 仍保持 100% 恢复。

| 保留率 R | 存储率 | 倍率 | 痕迹≥99% | 机制 |
|---|---|---|---|---|
| 1.0 | 35.0% | 2.86× | 100% ✅ | 纯去重（零删除） |
| 0.95 | 34.3% | 2.92× | 95.59% ❌ | 删 5% 唯一句 |
| 0.75 | 31.8% | 3.14× | 89.15% ❌ | 删 25% |
| 0.50 | 25.8% | 3.88× | 86.44% ❌ | 删 50% |
| 0.20 | 6.6% | 15.1× | 29.49% ❌ | 删 80% |

## 边界测试结果（295 痕迹判据，实测）

| 字典规模 | 存储率 | 倍率 | 位置级恢复 | 痕迹100% | ≥99% | 20题司南 |
|---|---|---|---|---|---|---|
| R=1.0 去重 | 35.02% | 2.86× | 1.0000 | 100% | 100% ✅ | 17/20 |
| dict 2000 | 25.73% | 3.89× | 无损 | 100% | 100% ✅ | 17/20 |
| dict 4000 | 25.19% | 3.97× | 无损 | 100% | 100% ✅ | 17/20 |
| dict 6000 | 24.84% | 4.03× | 无损 | 100% | 100% ✅ | 17/20 |
| dict 10000 | 24.34% | 4.11× | 无损 | 100% | 100% ✅ | 17/20 |
| dict 15000 | 23.94% | 4.18× | 无损 | 100% | 100% ✅ | 17/20 |
| dict 25000 | 23.51% | 4.25× | 无损 | 100% | 100% ✅ | 17/20 |
| dict 40000 | 23.13% | **4.32×** | **1.0000** | **100%** | **100% ✅** | 17/20 |
| dict40000+zlib | 8.39% | **11.93×** | **1.0000** | **100%** | **100% ✅** | 17/20 |

## 跨语料泛化（敌对盲测，2 个陌生域）

- 2 个从未见过的域（工具输出/搜索 dump 30MB + 理论专著 112KB）共 8 个配置
- 可达配置全部：字节级无损 100% PASS + 痕迹恢复 100% PASS
- 3× 档站稳（2.84×）；10× 档被超越（25×~45×）
- 4×/5× 在两域机制不可达（SCR 跳跃）——如实报告：倍率是域物理冗余的函数，不是旋钮

## 如何验证

- 全部产物 SHA-256 锁定；判据端与压缩端独立
- 压缩端输入 = 语料 + 字典规模，零测试目标泄漏
- 欢迎第三方独立验证。联系：GitHub Issues

## 合作 / 联系

寻找对 AI 长期记忆基础设施感兴趣的合作伙伴，进行真实 workload 联合基准验证。
如果你关心 AI 长期记忆的单位生命周期成本——存储、副本、传输、I/O、检索、上下文——欢迎联系。

潜在伙伴清单：见 `PARTNERS.md`。
