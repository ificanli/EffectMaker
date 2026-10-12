"""bd_guard（bdg 门禁）的单元测试。

覆盖：create 必填拦截、close reason 拦截、require-notes 拦截、guard-check 报告、_has_conclusion。
运行：python -m unittest workspace.tests.test_bd_guard -v
"""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest import mock

import workspace.tools.bd_guard as g


def ns(**kw) -> Namespace:
    base = {
        "description": "", "acceptance": "", "notes": "", "parent": "",
        "labels": "", "priority": None, "reason": "", "require_notes": False,
        "id": "", "text": "", "format": "text", "title": "t",
    }
    base.update(kw)
    return Namespace(**base)


class HasConclusionTests(unittest.TestCase):
    def test_notes_with_keyword_counts(self) -> None:
        self.assertTrue(g._has_conclusion("完成：产出知识卡片并沉淀到 knowledge/cards", []))
        self.assertTrue(g._has_conclusion("走了弯路：X→Y，最后用方案 Z 完成并记录", []))

    def test_comments_count(self) -> None:
        self.assertTrue(g._has_conclusion("", ["已沉淀 AESTHETIC-2026-001，结论完整"]))
        self.assertFalse(g._has_conclusion("", ["随便聊聊"]))

    def test_empty_fails(self) -> None:
        self.assertFalse(g._has_conclusion("", []))
        # 纯过程描述（无产出词）不算结论
        self.assertFalse(g._has_conclusion("尝试了方案A，然后方案B，最后方案C", []))
        # 太短的一两句不算结论
        self.assertFalse(g._has_conclusion("完成", []))
        # 评论里也没有产出词
        self.assertFalse(g._has_conclusion("", ["随便聊聊"]))


class CreateGuardTests(unittest.TestCase):
    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_missing_fields_rejected(self, mock_run: mock.Mock) -> None:
        code = g.cmd_create(ns(description="", acceptance="", notes=""))
        self.assertEqual(code, 2)
        mock_run.assert_not_called()

    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_partial_fields_rejected(self, mock_run: mock.Mock) -> None:
        code = g.cmd_create(ns(description="做什么", acceptance="", notes=""))
        self.assertEqual(code, 2)
        mock_run.assert_not_called()

    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_all_fields_passes(self, mock_run: mock.Mock) -> None:
        code = g.cmd_create(ns(
            title="任务A",
            description="做什么",
            acceptance="验收标准",
            notes="阶段记录/弯路",
            parent="vfx-zbh",
            labels="SRC-2026-UP389578709",
            priority=2,
        ))
        self.assertEqual(code, 0)
        args = mock_run.call_args.args[0]
        self.assertEqual(args[0], "create")
        self.assertIn("--acceptance", args)
        self.assertIn("--notes", args)
        self.assertIn("--parent", args)


class CloseGuardTests(unittest.TestCase):
    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_missing_reason_rejected(self, mock_run: mock.Mock) -> None:
        code = g.cmd_close(ns(id="vfx-x.1", reason="", require_notes=False))
        self.assertEqual(code, 2)
        mock_run.assert_not_called()

    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_reason_present_passes_without_require_notes(self, mock_run: mock.Mock) -> None:
        code = g.cmd_close(ns(id="vfx-x.1", reason="完成：产出卡片", require_notes=False))
        self.assertEqual(code, 0)
        args = mock_run.call_args.args[0]
        self.assertEqual(args[0], "close")

    @mock.patch("workspace.tools.bd_guard.load_issues")
    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_require_notes_missing_conclusion_rejected(self, mock_run: mock.Mock, mock_load: mock.Mock) -> None:
        mock_load.return_value = [
            {"id": "vfx-x.1", "notes": "", "comments": [], "status": "in_progress"},
        ]
        code = g.cmd_close(ns(id="vfx-x.1", reason="完成", require_notes=True))
        self.assertEqual(code, 2)
        mock_run.assert_not_called()

    @mock.patch("workspace.tools.bd_guard.load_issues")
    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_require_notes_with_conclusion_passes(self, mock_run: mock.Mock, mock_load: mock.Mock) -> None:
        mock_load.return_value = [
            {"id": "vfx-x.1", "notes": "弯路：A→B，最终用 C 方案完成并产出", "comments": [], "status": "in_progress"},
        ]
        code = g.cmd_close(ns(id="vfx-x.1", reason="完成", require_notes=True))
        self.assertEqual(code, 0)
        mock_run.assert_called_once()


class GuardCheckTests(unittest.TestCase):
    @mock.patch("workspace.tools.bd_guard.load_issues")
    def test_reports_noncompliant(self, mock_load: mock.Mock) -> None:
        mock_load.return_value = [
            {"id": "a-1", "title": "缺验收", "status": "open", "issue_type": "task",
             "acceptance_criteria": "", "close_reason": "", "notes": "", "comments": [], "labels": []},
            {"id": "a-2", "title": "合规", "status": "closed", "issue_type": "task",
             "acceptance_criteria": "有", "close_reason": "完成", "notes": "结论已沉淀", "comments": [], "labels": []},
            {"id": "a-3", "title": "legacy", "status": "closed", "issue_type": "task",
             "acceptance_criteria": "", "close_reason": "", "notes": "", "comments": [], "labels": ["legacy"]},
        ]
        report = g.cmd_guard_check(ns(format="json"))
        self.assertEqual(report, 1)  # 有不合规返回 1
        # 通过 json 输出验证（capture 用 redirect 略，这里直接看行为）

    @mock.patch("workspace.tools.bd_guard.load_issues")
    def test_all_compliant_returns_0(self, mock_load: mock.Mock) -> None:
        mock_load.return_value = [
            {"id": "b-1", "title": "好", "status": "closed", "issue_type": "task",
             "acceptance_criteria": "有", "close_reason": "完成", "notes": "结果已沉淀到知识库", "comments": [], "labels": []},
        ]
        code = g.cmd_guard_check(ns(format="text"))
        self.assertEqual(code, 0)

    def test_legacy_tag_constant(self) -> None:
        self.assertEqual(g.LEGACY_TAG, "legacy")


class ClaimTests(unittest.TestCase):
    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_claim_runs_update_claim(self, mock_run: mock.Mock) -> None:
        code = g.cmd_claim(ns(id="vfx-x.1"))
        self.assertEqual(code, 0)
        args = mock_run.call_args.args[0]
        self.assertEqual(args, ["update", "vfx-x.1", "--claim"])


class AcceptanceUpdateTests(unittest.TestCase):
    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_blank_acceptance_or_notes_never_writes(self, mock_run: mock.Mock) -> None:
        self.assertTrue(hasattr(g, "cmd_update"))
        for acceptance, notes in ((" ", "record"), ("criteria", " ")):
            self.assertEqual(2, g.cmd_update(ns(id="vfx-x.1", acceptance=acceptance, notes=notes)))
        mock_run.assert_not_called()

    @mock.patch("workspace.tools.bd_guard.run_bd")
    def test_update_appends_record_without_overwriting_history(self, mock_run: mock.Mock) -> None:
        self.assertTrue(hasattr(g, "cmd_update"))
        self.assertEqual(0, g.cmd_update(ns(id="vfx-x.1", acceptance="criteria", notes="record")))
        mock_run.assert_called_once_with(["update", "vfx-x.1", "--acceptance", "criteria", "--append-notes", "record"])

    def test_parser_limits_update_to_acceptance_and_record(self) -> None:
        self.assertTrue(hasattr(g, "cmd_update"))
        parsed = g.build_parser().parse_args(["update", "vfx-x.1", "--acceptance", "criteria", "--notes", "record"])
        self.assertIs(parsed.func, g.cmd_update)
        with self.assertRaises(SystemExit):
            g.build_parser().parse_args(["update", "vfx-x.1", "--status", "closed"])


if __name__ == "__main__":
    unittest.main()
