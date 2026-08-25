# JD 样本库（12 份）

> 对齐理论手册：4 种公司风格（大厂 / 创业 / 央国企 / 外企）× 各 3 份。  
> 用于简历对照评分、画像「与 JD 匹配度」、人才库按 JD 检索等。

## 索引

| 风格 | 文件 | 岗位 |
|------|------|------|
| 大厂 bigtech | `jd-bigtech-后端开发工程师.md` | 后端开发工程师（含「58 万笔/秒」串台教学数字） |
| 大厂 bigtech | `jd-bigtech-算法工程师.md` | 算法工程师（推荐/搜索） |
| 大厂 bigtech | `jd-bigtech-产品经理C端.md` | 产品经理（C 端增长） |
| 创业 startup | `jd-startup-后端开发工程师.md` | 后端开发工程师 |
| 创业 startup | `jd-startup-增长运营.md` | 增长运营 |
| 创业 startup | `jd-startup-产品经理.md` | 产品经理（ToB） |
| 央国企 soe | `jd-soe-软件开发工程师.md` | 软件开发工程师 |
| 央国企 soe | `jd-soe-数字化产品经理.md` | 数字化产品经理 |
| 央国企 soe | `jd-soe-HRBP.md` | HRBP |
| 外企 foreign | `jd-foreign-Software-Engineer.md` | Software Engineer |
| 外企 foreign | `jd-foreign-Product-Manager.md` | Product Manager |
| 外企 foreign | `jd-foreign-Marketing-Operations.md` | Marketing Operations |

## 使用提示

```bash
# 批量评分示例（对照大厂后端 JD + tech 简历）
python3 scoring/batch_score.py \
  jds/jd-bigtech-后端开发工程师.md \
  inbox \
  resume-tech \
  scoring/results/ranking-tech.json
```

**数字回核铁律**：回核基准只能是候选人原简历，**不能**把 JD 当基准（本库大厂后端 JD 含「58 万笔/秒」，正是串台教学用例）。

## 脱敏说明

所有 JD 中的「招聘公司」均为**虚构脱敏名称**（如「某头部互联网科技集团」「某 A 轮智能科技创业公司」），**不对应任何真实企业**。园区、地址、薪资带宽亦为比赛模拟数据。
