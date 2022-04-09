# Preempt_RT

#### Description
Linux in itself is not real time capable. With the additional PREEMPT_RT patch it gains real-time capabilities. The key point of the PREEMPT_RT patch is to minimize the amount of kernel code that is non-preemptible, while also minimizing the amount of code that must be changed in order to provide this added preemptibility. In particular, critical sections, interrupt handlers, and interrupt-disable code sequences are normally preemptible. The PREEMPT_RT patch leverages the SMP capabilities of the Linux kernel to add this extra preemptibility without requiring a complete kernel rewrite.

#### Software Architecture
Software architecture description

#### Installation

1.  xxxx
2.  xxxx
3.  xxxx

#### Instructions

1.  xxxx
2.  xxxx
3.  xxxx

#### Contribution

1.  Fork the repository
2.  Create Feat_xxx branch
3.  Commit your code
4.  Create Pull Request


#### Gitee Feature

1.  You can use Readme\_XXX.md to support different languages, such as Readme\_en.md, Readme\_zh.md
2.  Gitee blog [blog.gitee.com](https://blog.gitee.com)
3.  Explore open source project [https://gitee.com/explore](https://gitee.com/explore)
4.  The most valuable open source project [GVP](https://gitee.com/gvp)
5.  The manual of Gitee [https://gitee.com/help](https://gitee.com/help)
6.  The most popular members  [https://gitee.com/gitee-stars/](https://gitee.com/gitee-stars/)
