"""Create an idempotent demo course, materials, and accounts."""

# pylint: disable=line-too-long

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from AIQandA.models import Course, KnowledgeDocument
from AIQandA.services.documents import ingest_document

DOCUMENTS = [
    (
        "机器学习基础",
        "machine_learning_basics.txt",
        """机器学习基础

机器学习是让计算机从数据中学习规律，并利用规律对未知数据进行预测的方法。与手写规则的传统程序不同，机器学习模型通过训练数据调整参数，使预测误差尽量小。

按照学习信号的不同，机器学习通常分为监督学习、无监督学习和强化学习。监督学习使用带标签的数据，目标是学习输入到输出的映射；无监督学习不提供标签，重点发现数据内部的结构；强化学习则通过与环境交互获得的奖励信号来学习策略。

模型在训练集上表现好，不代表在新数据上表现好。过拟合是指模型把训练数据中的噪声和偶然细节也学了进去，导致训练误差很小但泛化误差较大。常见缓解方法包括增加训练数据、降低模型复杂度、使用正则化、早停和交叉验证。

欠拟合是指模型过于简单，连训练数据中的基本规律都没有学到。此时训练误差和验证误差都可能较高，需要增加特征、提高模型表达能力或延长训练时间。

通常把数据划分为训练集、验证集和测试集。训练集用于拟合参数，验证集用于选择超参数和早停，测试集只在最后评估一次，不能反复用来调参，否则会造成信息泄露和过于乐观的评估结果。""",
    ),
    (
        "监督学习与无监督学习",
        "supervised_vs_unsupervised.md",
        """# 监督学习与无监督学习

## 监督学习

监督学习（Supervised Learning）使用带标签的数据。每个样本都包含输入特征和对应的目标值，算法学习从特征到目标的映射。

- 分类：目标值是离散类别，例如判断邮件是否为垃圾邮件、识别图片中的动物。
- 回归：目标值是连续数值，例如预测房价、气温或考试分数。
- 常见算法：线性回归、逻辑回归、决策树、支持向量机、随机森林、神经网络。

监督学习的关键假设是训练数据与未来数据来自相近的分布。如果训练集和真实场景差异很大，模型效果会下降。

## 无监督学习

无监督学习（Unsupervised Learning）不提供目标标签，算法需要自己发现数据中的结构。

- 聚类：把相似样本分到同一组，例如用户分群、文档主题聚类。
- 降维：在尽量保留信息的前提下减少特征数量，例如主成分分析 PCA。
- 异常检测：发现与大多数样本明显不同的数据点。
- 常见算法：K-Means、层次聚类、DBSCAN、PCA。

## 两者的核心区别

| 维度 | 监督学习 | 无监督学习 |
| --- | --- | --- |
| 训练数据 | 有输入和标签 | 只有输入，没有标签 |
| 学习目标 | 学习输入到输出的映射 | 发现数据结构或模式 |
| 典型任务 | 分类、回归 | 聚类、降维、异常检测 |
| 评估方式 | 准确率、F1、均方误差等 | 轮廓系数、业务可解释性等 |

在实际项目中，两者也常结合使用：先用无监督学习做用户分群，再对有标签的部分做监督学习预测。""",
    ),
    (
        "模型评估",
        "model_evaluation.txt",
        """模型评估

评估模型时，不能只看准确率。准确率（Accuracy）是预测正确的样本数占总样本数的比例，但在类别不平衡时会产生误导。例如 99% 的样本都是负类，一个永远预测负类的模型也能得到 99% 的准确率，却没有任何识别正类的能力。

混淆矩阵把预测结果分为真正例（TP）、假正例（FP）、真负例（TN）和假负例（FN）。由此可以计算精确率、召回率和 F1 值。

精确率（Precision）表示预测为正例的样本中真正为正例的比例，关注“查得准不准”。召回率（Recall）表示真实正例中被找出来的比例，关注“查得全不全”。F1 值是精确率和召回率的调和平均，适合两者都需要兼顾的场景。

在垃圾邮件识别中，如果把正常邮件误判为垃圾邮件，代价可能很高，因此需要关注假正例和精确率。在疾病筛查中，漏掉真正患者代价很高，因此更关注召回率。选择什么指标，取决于业务目标，而不是指标本身。

交叉验证把数据分成多个折，轮流用其中一部分验证、其余部分训练，最后取平均结果。它比单次划分更稳定，尤其适合数据量较小的情况。交叉验证时，特征选择、归一化等预处理必须只在训练折上拟合，否则会把验证折的信息泄露进训练过程。

测试集应当保持独立，只在模型和超参数确定后使用一次。反复用测试集调参，相当于让模型间接看到了测试数据，最终报告的效果会过于乐观。""",
    ),
]


class Command(BaseCommand):
    """Populate a demo course and two accounts."""

    help = "Create the demo course, sample materials, and teacher/student accounts."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--password",
            default=os.getenv("DEMO_PASSWORD", ""),
            help="Password for the demo accounts (defaults to DEMO_PASSWORD).",
        )

    def handle(self, *args, **options) -> None:
        password = options["password"]
        if not password:
            raise CommandError("请通过 --password 或 DEMO_PASSWORD 提供演示账号密码。")

        user_model = get_user_model()
        teacher, _ = user_model.objects.get_or_create(
            username="teacher",
            defaults={
                "first_name": "肖",
                "last_name": "老师",
                "is_staff": True,
                "is_superuser": False,
            },
        )
        teacher.is_staff = True
        teacher.set_password(password)
        teacher.save()

        student, _ = user_model.objects.get_or_create(
            username="student",
            defaults={"first_name": "示例", "last_name": "学生"},
        )
        student.set_password(password)
        student.save()

        course, _ = Course.objects.update_or_create(
            code="AI101",
            defaults={
                "title": "人工智能导论",
                "description": "从机器学习基础到模型评估，面向初学者的 AI 入门课程。",
            },
        )

        created_documents = 0
        for title, filename, content in DOCUMENTS:
            if KnowledgeDocument.objects.filter(course=course, title=title).exists():
                continue
            document = KnowledgeDocument(
                course=course,
                uploaded_by=teacher,
                title=title,
            )
            document.file.save(
                filename,
                ContentFile(content.encode("utf-8")),
                save=False,
            )
            document.save()
            chunk_count = ingest_document(document)
            created_documents += 1
            self.stdout.write(f"  已索引《{title}》：{chunk_count} 个片段")

        self.stdout.write(self.style.SUCCESS("演示数据准备完成。"))
        self.stdout.write(f"  课程：{course.title} ({course.code})")
        self.stdout.write(f"  教师账号：teacher / {password}")
        self.stdout.write(f"  学生账号：student / {password}")
        self.stdout.write(f"  新增资料：{created_documents} 份")
