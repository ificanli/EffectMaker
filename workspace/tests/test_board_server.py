"""board_server 的单元测试。

覆盖：字段清洗、状态标签映射、epic 聚合、父标题查找、自然排序、CLI 入口。
运行：python -m unittest workspace.tests.test_board_server -v
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

import workspace.tools.board_server as board_server
from workspace.tools.board_server import (
    build_parser,
    compliance_problems,
    main,
    normalize,
    run_bd_list,
)

SAMPLE = [
    {
        "id": "vfx-2zo",
        "title": "游戏特效制作（18集，制作管道）",
        "status": "open",
        "priority": 1,
        "issue_type": "epic",
        "created_at": "2026-08-23T04:00:00Z",
        "updated_at": "2026-08-24T04:00:00Z",
        "labels": ["SRC-2026-GAMEVFX-001", "制作"],
        "notes": "长备注",
    },
    {
        "id": "vfx-2zo.1",
        "title": "场景搭建",
        "status": "open",
        "priority": 1,
        "issue_type": "task",
        "created_at": "2026-08-23T04:00:00Z",
        "updated_at": "2026-08-23T04:00:00Z",
        "labels": ["SRC-2026-GAMEVFX-001"],
        "parent": "vfx-2zo",
    },
    {
        "id": "vfx-2zo.2",
        "title": "后处理效果配置",
        "status": "in_progress",
        "priority": 1,
        "issue_type": "task",
        "created_at": "2026-08-23T04:00:00Z",
        "updated_at": "2026-08-24T04:00:00Z",
        "started_at": "2026-08-24T01:00:00Z",
        "labels": ["SRC-2026-GAMEVFX-001"],
        "parent": "vfx-2zo",
    },
    {
        "id": "vfx-2zo.3",
        "title": "烟花",
        "status": "closed",
        "priority": 1,
        "issue_type": "task",
        "created_at": "2026-08-23T04:00:00Z",
        "updated_at": "2026-08-24T02:00:00Z",
        "started_at": "2026-08-23T10:00:00Z",
        "closed_at": "2026-08-24T02:00:00Z",
        "close_reason": "完成",
        "labels": ["SRC-2026-GAMEVFX-001"],
        "parent": "vfx-2zo",
    },
    {
        "id": "vfx-mp7",
        "title": "作业点评系列（82集）",
        "status": "open",
        "priority": 1,
        "issue_type": "epic",
        "created_at": "2026-08-23T04:00:00Z",
        "updated_at": "2026-08-24T04:00:00Z",
        "labels": ["SRC-2026-SERIES-001"],
    },
]


class NormalizeTests(unittest.TestCase):
    """normalize 的字段清洗与派生计算。"""

    def setUp(self) -> None:
        self.issues, self.epics = normalize(SAMPLE)

    def test_field_cleaning_defaults(self) -> None:
        issue = next(i for i in self.issues if i["id"] == "vfx-2zo.1")
        self.assertEqual(issue["description"], "")
        self.assertEqual(issue["started_at"], "")
        self.assertEqual(issue["close_reason"], "")
        self.assertEqual(issue["acceptance_criteria"], "")
        self.assertEqual(issue["dependency_count"], 0)
        self.assertEqual(issue["comment_count"], 0)
        self.assertEqual(issue["labels"], ["SRC-2026-GAMEVFX-001"])

    def test_priority_passthrough(self) -> None:
        issue = next(i for i in self.issues if i["id"] == "vfx-2zo.3")
        self.assertEqual(issue["priority"], 1)

    def test_parent_title_resolved(self) -> None:
        issue = next(i for i in self.issues if i["id"] == "vfx-2zo.1")
        self.assertEqual(issue["parent_title"], "游戏特效制作（18集，制作管道）")

    def test_parent_title_fallback_to_id(self) -> None:
        orphan = {
            "id": "x-1",
            "title": "孤儿任务",
            "status": "open",
            "priority": 2,
            "issue_type": "task",
            "parent": "not-exist",
        }
        issues, _ = normalize(SAMPLE + [orphan])
        found = next(i for i in issues if i["id"] == "x-1")
        self.assertEqual(found["parent_title"], "not-exist")

    def test_natural_sort(self) -> None:
        ids = [i["id"] for i in self.issues]
        self.assertEqual(ids.index("vfx-2zo.2"), ids.index("vfx-2zo.1") + 1)
        self.assertEqual(ids.index("vfx-2zo.3"), ids.index("vfx-2zo.2") + 1)
        # 数字后缀的自然序：vfx-mp7.10 应排在 vfx-mp7.2 之后（字典序会把 .10 排在 .2 前）
        raw = SAMPLE + [
            {"id": "vfx-mp7.1", "title": "第01集", "status": "open", "priority": 2, "issue_type": "task", "parent": "vfx-mp7"},
            {"id": "vfx-mp7.2", "title": "第02集", "status": "open", "priority": 2, "issue_type": "task", "parent": "vfx-mp7"},
            {"id": "vfx-mp7.10", "title": "第10集", "status": "open", "priority": 2, "issue_type": "task", "parent": "vfx-mp7"},
        ]
        issues, _ = normalize(raw)
        order = [i["id"] for i in issues]
        self.assertLess(order.index("vfx-mp7.1"), order.index("vfx-mp7.2"))
        self.assertLess(order.index("vfx-mp7.2"), order.index("vfx-mp7.10"))

    def test_epics_aggregation(self) -> None:
        epic = next(e for e in self.epics if e["id"] == "vfx-2zo")
        self.assertEqual(epic["total"], 3)
        self.assertEqual(epic["done"], 1)
        self.assertEqual(epic["series"], "SRC-2026-GAMEVFX-001")
        children_ids = [c["id"] for c in epic["children"]]
        self.assertEqual(children_ids, ["vfx-2zo.1", "vfx-2zo.2", "vfx-2zo.3"])

    def test_epics_include_only_epic_type(self) -> None:
        self.assertEqual([e["id"] for e in self.epics], ["vfx-2zo", "vfx-mp7"])

    def test_epics_series_empty_when_no_src_label(self) -> None:
        plain = {
            "id": "plain-1",
            "title": "无标签epic",
            "status": "open",
            "priority": 2,
            "issue_type": "epic",
            "labels": ["杂项"],
        }
        _, epics = normalize(SAMPLE + [plain])
        found = next(e for e in epics if e["id"] == "plain-1")
        self.assertEqual(found["series"], "")


class ComplianceTests(unittest.TestCase):
    """compliance_problems 与 normalize 的 problems 字段。"""

    def _issue(self, **over) -> dict:
        base = {
            "id": "t-1", "title": "任务", "status": "open", "priority": 2,
            "issue_type": "task", "acceptance_criteria": "有验收", "close_reason": "",
            "notes": "", "comments": [], "labels": [],
        }
        base.update(over)
        return base

    def test_missing_acceptance(self) -> None:
        self.assertIn("缺验收标准", compliance_problems(self._issue(acceptance_criteria="")))

    def test_open_with_acceptance_ok(self) -> None:
        self.assertEqual(compliance_problems(self._issue()), [])

    def test_closed_missing_reason(self) -> None:
        p = compliance_problems(self._issue(status="closed", close_reason="", notes="完成：已沉淀结论"))
        self.assertIn("closed 缺 close_reason", p)

    def test_closed_no_conclusion(self) -> None:
        p = compliance_problems(self._issue(status="closed", close_reason="完成", notes=""))
        self.assertIn("closed 无结论记录", p)

    def test_closed_compliant(self) -> None:
        p = compliance_problems(self._issue(status="closed", close_reason="完成", notes="结果已沉淀到知识库"))
        self.assertEqual(p, [])

    def test_legacy_exempt(self) -> None:
        p = compliance_problems(self._issue(labels=["legacy"], acceptance_criteria=""))
        self.assertEqual(p, [])

    def test_normalize_sets_problems(self) -> None:
        issues, _ = normalize(SAMPLE)
        task = next(i for i in issues if i["id"] == "vfx-2zo.1")  # 缺验收标准
        self.assertIn("缺验收标准", task["problems"])


class RunBdListTests(unittest.TestCase):
    """run_bd_list 对子进程的封装。"""

    @mock.patch("workspace.tools.board_server.shutil.which")
    @mock.patch("workspace.tools.board_server.subprocess.run")
    def test_parses_json(self, mock_run: mock.Mock, mock_which: mock.Mock) -> None:
        # 前两次 npm 探测返回空（跳过），第三次 bd list 返回数据
        mock_which.return_value = "bd"
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="", stderr=""),   # npm prefix -g
            mock.Mock(returncode=0, stdout="", stderr=""),   # npm root -g
            mock.Mock(returncode=0, stdout='[{"id": "a-1", "status": "open"}]', stderr=""),
        ]
        data = run_bd_list()
        self.assertEqual(data, [{"id": "a-1", "status": "open"}])
        args = mock_run.call_args.args[0]
        # Windows 下 _bd_cmd() 解析出 bd.cmd 实际路径，断言命令末尾即可
        self.assertEqual(args[-4:], ["list", "--all", "--format", "json"])

    @mock.patch("workspace.tools.board_server.shutil.which")
    @mock.patch("workspace.tools.board_server.subprocess.run")
    def test_nonzero_exit_raises(self, mock_run: mock.Mock, mock_which: mock.Mock) -> None:
        mock_which.return_value = "bd"
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="", stderr=""),    # npm prefix -g
            mock.Mock(returncode=0, stdout="", stderr=""),    # npm root -g
            mock.Mock(returncode=1, stdout="", stderr="bd not found"),
        ]
        with self.assertRaises(RuntimeError) as ctx:
            run_bd_list()
        self.assertIn("bd not found", str(ctx.exception))

    @mock.patch("workspace.tools.board_server.shutil.which")
    @mock.patch("workspace.tools.board_server.subprocess.run")
    def test_invalid_json_raises(self, mock_run: mock.Mock, mock_which: mock.Mock) -> None:
        mock_which.return_value = "bd"
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="", stderr=""),    # npm prefix -g
            mock.Mock(returncode=0, stdout="", stderr=""),    # npm root -g
            mock.Mock(returncode=0, stdout="not json", stderr=""),
        ]
        with self.assertRaises(RuntimeError):
            run_bd_list()


class CliTests(unittest.TestCase):
    """CLI 入口：参数解析与子进程失败时返回非零退出码。"""

    def test_build_parser_defaults(self) -> None:
        ns = build_parser().parse_args([])
        self.assertEqual(ns.port, 8611)
        self.assertFalse(ns.no_browser)

    @mock.patch("workspace.tools.board_server.run_bd_list", side_effect=RuntimeError("boom"))
    def test_run_bd_failure_propagates(self, mock_run: mock.Mock) -> None:
        # 数据源失败时异常向调用方抛出（页面会显示 500 + 错误信息）
        with self.assertRaises(RuntimeError):
            board_server.run_bd_list()
        mock_run.assert_called_once()

    @mock.patch("workspace.tools.board_server.shutil.which")
    @mock.patch("workspace.tools.board_server.subprocess.run")
    @mock.patch("workspace.tools.board_server.os.name", new="nt")
    def test_bd_cmd_windows_resolves_cmd(self, mock_run: mock.Mock, mock_which: mock.Mock) -> None:
        # Windows 下优先 npm prefix -g 的 bin 目录（真实 bd.cmd 所在，绕过 PATH 守卫）
        # os.name 用 new="nt" 固定值（不注入参数）；subprocess.run → which 自下而上注入
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout=r"C:\Users\luxinyu\AppData\Roaming\npm", stderr=""),
            mock.Mock(returncode=0, stdout=r"C:\Users\luxinyu\AppData\Roaming\npm\node_modules", stderr=""),
        ]
        from workspace.tools.board_server import _bd_cmd

        self.assertEqual(_bd_cmd(), [r"C:\Users\luxinyu\AppData\Roaming\npm\bd.cmd"])
        self.assertFalse(mock_which.called)

    @mock.patch("workspace.tools.board_server.shutil.which")
    @mock.patch("workspace.tools.board_server.subprocess.run")
    @mock.patch("workspace.tools.board_server.os.name", new="nt")
    def test_bd_cmd_falls_back_to_which_when_no_npm(self, mock_run: mock.Mock, mock_which: mock.Mock) -> None:
        # npm 全局 bin/root 目录都没有 bd.cmd 时回退到 which
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
        ]
        mock_which.return_value = r"D:\tools\bd.cmd"
        from workspace.tools.board_server import _bd_cmd

        self.assertEqual(_bd_cmd(), [r"D:\tools\bd.cmd"])


if __name__ == "__main__":
    unittest.main()
