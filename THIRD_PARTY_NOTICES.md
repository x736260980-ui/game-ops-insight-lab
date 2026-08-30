# 第三方组件说明

## MediaCrawler

本项目通过 Git 子模块使用 [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)，固定兼容提交为：

```text
d6f7c5bb906b6dac40ddf343ef9e26438a3de092
```

MediaCrawler 使用 `NON-COMMERCIAL LEARNING LICENSE 1.1`，仅限非商业学习与研究用途。其许可证、版权声明和使用边界以 `source/LICENSE` 为准，不受本项目 MIT License 覆盖。

使用采集能力时应遵守目标平台条款、robots.txt、当地法律法规与合理请求频率，不得用于大规模抓取、平台干扰或商业用途。

## Distilly

本项目的实验性 Player Persona 蒸馏流程参考并可选使用 [titanwings/distilly](https://github.com/titanwings/distilly)。Distilly 使用 MIT License，版权归其原作者所有。

Distilly 当前不作为本仓库子模块或打包依赖分发。需要 Persona 蒸馏时，应从上游仓库单独安装，并遵守其许可证与数据使用说明。用户必须只使用自己拥有合法处理权限的材料，不得上传私人聊天、身份信息或未经授权的数据。

## 其他依赖

Python 与前端依赖分别由 `requirements.txt`、`source/requirements.txt` 和 `insight-dashboard/package-lock.json` 声明，各自适用其上游许可证。
