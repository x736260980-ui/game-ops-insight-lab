import asyncio
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("run_dual_agent.py")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUITE_REFERENCES = PROJECT_ROOT / ".agents" / "skills" / "game-ops-insight-suite" / "references"
DUAL_SKILL_PATH = SUITE_REFERENCES / "dual-agent-protocol.md"
SINGLE_SKILL_PATH = SUITE_REFERENCES / "single-agent-analysis.md"
SPEC = importlib.util.spec_from_file_location("run_dual_agent", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def raw_reply(body, control):
    return body + "\n<CONTROL_JSON>\n" + json.dumps(control, ensure_ascii=False) + "\n</CONTROL_JSON>"


def open_control():
    return {
        "action": "OPEN",
        "issue": {
            "title": "玩家伤害来自补偿不足还是消费拉力",
            "opponent_claim": "改动已经充分补偿老玩家",
            "own_position": "补偿高度依赖新增资源",
            "evidence_refs": ["DY-0001"],
            "material_impact": "player_harm",
        },
    }


def pass_control():
    return {"action": "PASS", "reason": "没有新的实质分歧"}


def action_control(action, issue_id, *, close_status=None, close_reason=None):
    value = {"action": action, "issue_id": issue_id, "evidence_refs": ["DY-0002"]}
    if action in {"REBUT", "FINAL_ANSWER"}:
        value["close_status"] = close_status
        value["close_reason"] = close_reason
    return value


def discussion_reply(control, body="这是针对当前议题的完整讨论正文。"):
    return MODULE.DiscussionReply(body, control)


class DualAgentV4Test(unittest.TestCase):
    def test_prompt_delivery_does_not_wait_for_windows_stdin_handle_release(self):
        class FakeStdin:
            def __init__(self):
                self.written = b""
                self.drained = False
                self.closed = False
                self.wait_closed_called = False

            def write(self, value):
                self.written += value

            async def drain(self):
                self.drained = True

            def close(self):
                self.closed = True

            async def wait_closed(self):
                self.wait_closed_called = True
                await asyncio.Event().wait()

        async def scenario():
            stdin = FakeStdin()
            await MODULE.deliver_prompt(stdin, "中文提示")
            self.assertEqual(stdin.written, "中文提示".encode("utf-8"))
            self.assertTrue(stdin.drained)
            self.assertTrue(stdin.closed)
            self.assertFalse(stdin.wait_closed_called)

        asyncio.run(scenario())

    def test_dual_skill_uses_causal_methods_and_human_dialogue(self):
        skill = DUAL_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("预期优先", skill)
        self.assertIn("体验优先", skill)
        self.assertIn("像两个熟悉业务的人当面聊", skill)
        self.assertIn("不是预设立场", skill)
        self.assertNotIn("准确呈现对方最强的证据或推理", skill)
        self.assertNotIn("给出当前裁决", skill)
        self.assertNotIn("必须用另一条路径反证自己", skill)

    def test_dual_skill_defines_one_neutral_final_report_mode(self):
        skill = DUAL_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("`final_report`", skill)
        self.assertIn("终稿整理者", skill)
        self.assertIn("不得默认自己的初审优先", skill)
        self.assertIn("证据不足", skill)
        self.assertNotIn("`revised_report`", skill)

    def test_dual_skill_and_every_agent_prompt_require_utf8_file_reading(self):
        skill = DUAL_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("UTF-8", skill)
        self.assertIn("乱码", skill)

        blind = MODULE.blind_prompt(
            "主题", [Path("E:/analysis-input.json")], "Claude B",
            MODULE.analysis_method("codex"),
        )
        nomination = MODULE.nomination_prompt(
            topic="主题", agent="codex", own_initial=Path("E:/a.md"),
            opponent_initial=Path("E:/b.md"),
        )
        discussion = MODULE.discussion_prompt(
            topic="主题",
            step={"action": "OPEN_OR_PASS", "speaker": "codex", "slot_index": 0, "issue_turn": 1},
            discussion=MODULE.empty_discussion(), entries=[],
            own_initial=Path("E:/a.md"), opponent_initial=Path("E:/b.md"),
        )
        final_report = MODULE.final_report_prompt(
            topic="主题", materials=[Path("E:/analysis-input.json")],
            codex_initial=Path("E:/a.md"), claude_initial=Path("E:/b.md"),
            transcript=Path("E:/transcript.md"), disputes_path=Path("E:/disputes.json"),
        )
        final_summary = MODULE.final_summary_prompt(Path("E:/05-final-analysis.md"))
        for prompt in (blind, nomination, discussion, final_report, final_summary):
            self.assertIn("UTF-8", prompt)
            self.assertIn("乱码", prompt)
        self.assertIn("risk` 和 `confidence` 必须是顶层同级字段", final_summary)
        self.assertIn("不得把 `confidence` 嵌套在 `risk` 中", final_summary)

    def test_single_skill_compares_expectation_and_experience_paths(self):
        skill = SINGLE_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("预期路径", skill)
        self.assertIn("体验路径", skill)
        self.assertIn("首要根因", skill)
        self.assertIn("反事实", skill)
        self.assertNotIn("下降 70%", skill)

    def test_authoritative_output_contract(self):
        self.assertEqual(MODULE.APP_VERSION, "5.0")
        self.assertEqual(MODULE.OUTPUT_DIR_NAME, "dual-agent")
        state = MODULE.initial_state(Path("E:/demo"), "主题", "gpt", "medium", "deepseek", False)
        self.assertEqual(state["schema_version"], "dual-game-ops-run-5.0")
        self.assertFalse(state["swap_methods"])

    def test_low_cost_models_are_the_defaults(self):
        self.assertEqual(MODULE.DEFAULT_CODEX_MODEL, "gpt-5.6-luna")
        self.assertEqual(MODULE.DEFAULT_CODEX_REASONING, "medium")
        self.assertEqual(MODULE.DEFAULT_CLAUDE_MODEL, "deepseek-v4-flash[1m]")

    def test_stage_timeouts_allow_complete_non_streaming_answers(self):
        self.assertEqual(MODULE.turn_timeout_for("initial"), 600)
        self.assertEqual(MODULE.turn_timeout_for("nomination"), 120)
        self.assertEqual(MODULE.turn_timeout_for("discussion"), 120)
        self.assertEqual(MODULE.turn_timeout_for("final_report"), 600)
        self.assertEqual(MODULE.turn_timeout_for("final_summary"), 120)

    def test_analysis_methods_are_distinct_and_swappable(self):
        self.assertEqual(MODULE.analysis_method("codex", False)["key"], "expectation_first")
        self.assertEqual(MODULE.analysis_method("claude", False)["key"], "experience_first")
        self.assertEqual(MODULE.analysis_method("codex", True)["key"], "experience_first")
        self.assertEqual(MODULE.analysis_method("claude", True)["key"], "expectation_first")

    def test_blind_prompt_uses_method_as_starting_point_not_fixed_position(self):
        prompt = MODULE.blind_prompt(
            "研究主题", [Path("E:/analysis-input.json")], "Claude B",
            MODULE.analysis_method("codex", False),
        )
        self.assertIn("预期优先", prompt)
        self.assertIn("思考起点", prompt)
        self.assertIn("不是预设结论", prompt)
        self.assertIn("首要根因", prompt)
        self.assertNotIn("下降 70%", prompt)
        self.assertNotIn("显著降级", prompt)
    def test_single_issue_limits_are_hard_locked(self):
        self.assertEqual(MODULE.MAX_ISSUES_PER_AGENT, 2)
        self.assertEqual(MODULE.MAX_ISSUES_TOTAL, 4)
        self.assertEqual(MODULE.MAX_TURNS_PER_ISSUE, 4)
        self.assertEqual(MODULE.MAX_TURN_CHARS, 1000)
        self.assertEqual(MODULE.ISSUE_OWNER_ORDER, ("codex", "claude", "codex", "claude"))
        self.assertFalse(hasattr(MODULE, "MAX_ROUNDS"))

    def test_empty_discussion_offers_first_slot_to_codex(self):
        step = MODULE.next_discussion_step(MODULE.empty_discussion())
        self.assertEqual(step["action"], "OPEN_OR_PASS")
        self.assertEqual(step["speaker"], "codex")
        self.assertEqual(step["slot_index"], 0)

    def test_parallel_nominations_fill_a1_b1_a2_b2_slots(self):
        discussion = MODULE.empty_discussion()
        a_candidates = [
            {"title": "A一", "opponent_claim": "B判断一", "own_position": "A判断一", "evidence_refs": ["A-1"], "material_impact": "player_harm"},
            {"title": "A二", "opponent_claim": "B判断二", "own_position": "A判断二", "evidence_refs": ["A-2"], "material_impact": "mechanism_effect"},
        ]
        b_candidates = [
            {"title": "B一", "opponent_claim": "A判断一", "own_position": "B判断一", "evidence_refs": ["B-1"], "material_impact": "emotion_groups"},
        ]
        MODULE.apply_nominations(discussion, "codex", a_candidates)
        MODULE.apply_nominations(discussion, "claude", b_candidates)
        self.assertEqual([slot.get("candidate", {}).get("title") for slot in discussion["slots"]], ["A一", "B一", "A二", None])
        self.assertEqual(discussion["slots"][3]["status"], "PASSED")

    def test_nomination_prompt_allows_zero_to_two_and_reads_both_initials(self):
        prompt = MODULE.nomination_prompt(
            topic="主题", agent="codex", own_initial=Path("E:/a.md"), opponent_initial=Path("E:/b.md")
        )
        self.assertIn("0—2", prompt)
        self.assertIn("E:\\a.md", prompt)
        self.assertIn("E:\\b.md", prompt)
        self.assertIn("NOMINATION_JSON", prompt)
        self.assertIn("不要为了热闹", prompt)

    def test_only_one_current_issue_is_allowed(self):
        discussion = MODULE.empty_discussion()
        discussion["items"] = [
            {"id": "A-Q001", "status": "CURRENT"},
            {"id": "B-Q001", "status": "CURRENT"},
        ]
        with self.assertRaises(MODULE.WorkflowError):
            MODULE.next_discussion_step(discussion)

    def test_discussion_body_accepts_1000_and_rejects_1001_characters(self):
        step = {"action": "OPEN_OR_PASS", "speaker": "codex", "slot_index": 0}
        parsed = MODULE.parse_discussion_reply(raw_reply("甲" * 1000, open_control()), step)
        self.assertEqual(len(parsed.body), 1000)
        with self.assertRaises(MODULE.WorkflowError):
            MODULE.parse_discussion_reply(raw_reply("甲" * 1001, open_control()), step)

    def test_simple_acceptance_is_not_semantically_rejected(self):
        step = {"action": "REBUT", "speaker": "codex", "issue_id": "A-Q001", "issue_turn": 3}
        control = action_control("REBUT", "A-Q001", close_status="RESOLVED", close_reason="接受")
        parsed = MODULE.parse_discussion_reply(raw_reply("接受。", control), step)
        self.assertEqual(parsed.body, "接受。")

    def test_single_issue_lifecycle_runs_in_strict_order(self):
        discussion = MODULE.empty_discussion()
        open_step = MODULE.next_discussion_step(discussion)
        MODULE.apply_discussion_reply(discussion, open_step, discussion_reply(open_control()))
        self.assertEqual(discussion["items"][0]["id"], "A-Q001")
        self.assertEqual(discussion["items"][0]["status"], "CURRENT")
        self.assertEqual(discussion["items"][0]["turn_count"], 1)

        answer_step = MODULE.next_discussion_step(discussion)
        self.assertEqual((answer_step["speaker"], answer_step["action"], answer_step["issue_turn"]), ("claude", "ANSWER", 2))
        MODULE.apply_discussion_reply(
            discussion, answer_step,
            discussion_reply(action_control("ANSWER", "A-Q001")),
        )

        rebut_step = MODULE.next_discussion_step(discussion)
        self.assertEqual((rebut_step["speaker"], rebut_step["action"], rebut_step["issue_turn"]), ("codex", "REBUT", 3))
        MODULE.apply_discussion_reply(
            discussion, rebut_step,
            discussion_reply(action_control("REBUT", "A-Q001")),
        )

        final_step = MODULE.next_discussion_step(discussion)
        self.assertEqual((final_step["speaker"], final_step["action"], final_step["issue_turn"]), ("claude", "FINAL_ANSWER", 4))
        MODULE.apply_discussion_reply(
            discussion, final_step,
            discussion_reply(action_control(
                "FINAL_ANSWER", "A-Q001", close_status="UNRESOLVED", close_reason="风险阈值不同"
            )),
        )
        self.assertEqual(discussion["items"][0]["status"], "UNRESOLVED")
        next_slot = MODULE.next_discussion_step(discussion)
        self.assertEqual((next_slot["speaker"], next_slot["slot_index"]), ("claude", 1))

    def test_owner_can_close_at_rebut_and_move_to_next_slot(self):
        discussion = MODULE.empty_discussion()
        MODULE.apply_discussion_reply(discussion, MODULE.next_discussion_step(discussion), discussion_reply(open_control()))
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion),
            discussion_reply(action_control("ANSWER", "A-Q001")),
        )
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion),
            discussion_reply(action_control(
                "REBUT", "A-Q001", close_status="RESOLVED", close_reason="关键反例改变了原判断"
            )),
        )
        self.assertEqual(discussion["items"][0]["status"], "RESOLVED")
        self.assertEqual(MODULE.next_discussion_step(discussion)["speaker"], "claude")

    def test_pass_consumes_slot_without_creating_issue(self):
        discussion = MODULE.empty_discussion()
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion), discussion_reply(pass_control(), "没有新议题。")
        )
        self.assertEqual(discussion["slots"][0]["status"], "PASSED")
        self.assertEqual(discussion["items"], [])
        self.assertEqual(MODULE.next_discussion_step(discussion)["speaker"], "claude")

    def test_invalid_discussion_application_is_atomic(self):
        discussion = MODULE.empty_discussion()
        before = json.dumps(discussion, ensure_ascii=False, sort_keys=True)
        invalid = discussion_reply({"action": "ANSWER", "issue_id": "A-Q999", "evidence_refs": []})
        with self.assertRaises(MODULE.WorkflowError):
            MODULE.apply_discussion_reply(discussion, MODULE.next_discussion_step(discussion), invalid)
        self.assertEqual(json.dumps(discussion, ensure_ascii=False, sort_keys=True), before)

    def test_answer_prompt_focuses_only_on_current_issue(self):
        discussion = MODULE.empty_discussion()
        MODULE.apply_discussion_reply(discussion, MODULE.next_discussion_step(discussion), discussion_reply(open_control()))
        step = MODULE.next_discussion_step(discussion)
        prompt = MODULE.discussion_prompt(
            topic="研究主题",
            step=step,
            discussion=discussion,
            entries=[{"issue_id": "A-Q001", "issue_turn": 1, "agent": "codex", "text": "A的完整立题"}],
            own_initial=Path("E:/own-initial.md"),
            opponent_initial=Path("E:/opponent-initial.md"),
        )
        self.assertIn("A-Q001", prompt)
        self.assertIn("A的完整立题", prompt)
        self.assertIn("E:\\own-initial.md", prompt)
        self.assertIn("E:\\opponent-initial.md", prompt)
        self.assertIn("1000", prompt)
        self.assertIn("不得开启新议题", prompt)
        self.assertIn("像两个熟悉业务的人当面聊", prompt)
        self.assertNotIn("复述对方最强论点", prompt)
        self.assertNotIn("给出当前裁决", prompt)
        self.assertNotIn("部分修正、完全修正", prompt)

    def test_final_report_prompt_uses_both_initials_and_preserves_unresolved_issues(self):
        prompt = MODULE.final_report_prompt(
            topic="研究主题", materials=[Path("E:/analysis-input.json")],
            codex_initial=Path("E:/codex.md"), claude_initial=Path("E:/claude.md"),
            transcript=Path("E:/talk.md"), disputes_path=Path("E:/issues.json"),
        )
        self.assertIn("终稿整理者", prompt)
        self.assertIn("E:\\codex.md", prompt)
        self.assertIn("E:\\claude.md", prompt)
        self.assertIn("不得默认自己的初审优先", prompt)
        self.assertIn("证据不足", prompt)
        self.assertIn("保留", prompt)

    def test_final_report_cleanup_drops_model_process_preamble(self):
        raw = "三份过程材料已全部读取，以下为最终报告。\n\n---\n\n# 正式标题\n\n正文。"

        cleaned = MODULE.clean_final_report(raw)

        self.assertEqual(cleaned, "# 正式标题\n\n正文。\n")

    def test_final_summary_protocol_and_risk_mapping(self):
        valid = {
            "schema_version": "game-ops-final-summary-1.0",
            "research_title": "绯英 PV 争议",
            "core_judgment": "质量不足被规格差异升级为待遇不公叙事。",
            "risk": {"score": 0.6, "level": "middle", "rationale": "风险集中但尚无规模证据。"},
            "confidence": {"level": "middle", "rationale": "评论充分，官方信息不足。"},
            "key_findings": ["基础体验伤口明确", "公平叙事构成放大器"],
            "operation_directions": ["补足角色表达", "处理规格差异感知"],
            "evidence_refs": ["DY-0004", "XHS-0237", "WEB-001"],
            "evidence_gaps": ["缺少官方对调整原因的说明"],
        }
        self.assertEqual(MODULE.parse_final_summary(json.dumps(valid, ensure_ascii=False)), valid)
        self.assertEqual(MODULE.risk_level_for_score(0.0), "low")
        self.assertEqual(MODULE.risk_level_for_score(0.3), "low")
        self.assertEqual(MODULE.risk_level_for_score(0.4), "middle")
        self.assertEqual(MODULE.risk_level_for_score(0.6), "middle")
        self.assertEqual(MODULE.risk_level_for_score(0.7), "high")
        self.assertEqual(MODULE.risk_level_for_score(1.0), "high")
        invalid = json.loads(json.dumps(valid, ensure_ascii=False))
        invalid["risk"]["level"] = "high"
        with self.assertRaises(MODULE.WorkflowError):
            MODULE.parse_final_summary(json.dumps(invalid, ensure_ascii=False))
        nested = json.loads(json.dumps(valid, ensure_ascii=False))
        nested["risk"]["confidence"] = nested.pop("confidence")
        with self.assertRaisesRegex(MODULE.WorkflowError, "缺少=.*confidence"):
            MODULE.parse_final_summary(json.dumps(nested, ensure_ascii=False))

    def test_open_prompt_includes_previous_topics_and_remaining_quota(self):
        discussion = MODULE.empty_discussion()
        MODULE.apply_discussion_reply(discussion, MODULE.next_discussion_step(discussion), discussion_reply(open_control()))
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion),
            discussion_reply(action_control("ANSWER", "A-Q001")),
        )
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion),
            discussion_reply(action_control("REBUT", "A-Q001", close_status="RESOLVED", close_reason="已解决")),
        )
        step = MODULE.next_discussion_step(discussion)
        prompt = MODULE.discussion_prompt(
            topic="研究主题", step=step, discussion=discussion, entries=[],
            own_initial=Path("E:/b.md"), opponent_initial=Path("E:/a.md"),
        )
        self.assertIn("玩家伤害来自补偿不足还是消费拉力", prompt)
        self.assertIn("剩余议题名额", prompt)
        self.assertIn("OPEN", prompt)
        self.assertIn("PASS", prompt)

    def test_open_prompt_counts_remaining_slots_after_passes(self):
        discussion = MODULE.empty_discussion()
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion),
            discussion_reply(pass_control(), "没有新的实质分歧。"),
        )
        MODULE.apply_discussion_reply(discussion, MODULE.next_discussion_step(discussion), discussion_reply(open_control()))
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion),
            discussion_reply(action_control("ANSWER", "B-Q001")),
        )
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion),
            discussion_reply(action_control("REBUT", "B-Q001", close_status="RESOLVED", close_reason="已解决")),
        )
        step = MODULE.next_discussion_step(discussion)
        self.assertEqual((step["speaker"], step["slot_index"]), ("codex", 2))
        prompt = MODULE.discussion_prompt(
            topic="研究主题", step=step, discussion=discussion, entries=[],
            own_initial=Path("E:/a.md"), opponent_initial=Path("E:/b.md"),
        )
        self.assertIn("剩余议题名额：1/2", prompt)

    def test_two_consecutive_cross_agent_passes_finish_early(self):
        discussion = MODULE.empty_discussion()
        speakers = []
        while (step := MODULE.next_discussion_step(discussion)) is not None:
            speakers.append(step["speaker"])
            MODULE.apply_discussion_reply(
                discussion, step, discussion_reply(pass_control(), "没有新的实质分歧。")
            )
        self.assertEqual(speakers, ["codex", "claude"])
        self.assertEqual([slot["status"] for slot in discussion["slots"]], ["PASSED", "PASSED", "PENDING", "PENDING"])

    def test_resume_uses_current_issue_turn_count(self):
        discussion = MODULE.empty_discussion()
        MODULE.apply_discussion_reply(discussion, MODULE.next_discussion_step(discussion), discussion_reply(open_control()))
        MODULE.apply_discussion_reply(
            discussion, MODULE.next_discussion_step(discussion),
            discussion_reply(action_control("ANSWER", "A-Q001")),
        )
        resumed = MODULE.next_discussion_step(json.loads(json.dumps(discussion, ensure_ascii=False)))
        self.assertEqual((resumed["speaker"], resumed["action"], resumed["issue_turn"]), ("codex", "REBUT", 3))

    def test_transcript_groups_messages_by_single_issue(self):
        discussion = MODULE.empty_discussion()
        discussion["slots"][0].update({"status": "PASSED", "reason": "没有新的实质分歧"})
        discussion["slots"][1].update({"status": "COMPLETED", "issue_id": "B-Q001"})
        discussion["items"].append({
            "id": "B-Q001", "slot_index": 1, "owner": "claude", "target": "codex",
            "title": "专武属于普通贬值还是商品信任伤害", "opponent_claim": "属于一般资产贬值",
            "own_position": "应独立视为商品信任伤害", "evidence_refs": ["DY-0006"],
            "material_impact": "player_harm", "status": "UNRESOLVED", "turn_count": 4,
            "close_reason": "双方对商品承诺边界仍有不同判断",
        })
        entries = [
            {"slot_index": 0, "issue_id": None, "issue_turn": 0, "agent": "codex", "action": "PASS", "text": "没有新议题。"},
            {"slot_index": 1, "issue_id": "B-Q001", "issue_turn": 1, "agent": "claude", "action": "OPEN", "text": "B提出议题。"},
            {"slot_index": 1, "issue_id": "B-Q001", "issue_turn": 2, "agent": "codex", "action": "ANSWER", "text": "A回答。"},
            {"slot_index": 1, "issue_id": "B-Q001", "issue_turn": 3, "agent": "claude", "action": "REBUT", "text": "B复核。"},
            {"slot_index": 1, "issue_id": "B-Q001", "issue_turn": 4, "agent": "codex", "action": "FINAL_ANSWER", "text": "A最终回应。"},
        ]
        transcript = MODULE.render_transcript(entries, discussion, "issue_queue_completed")
        self.assertIn("议题 B-Q001", transcript)
        self.assertIn("第 1/4 次发言 · Claude B · 立题", transcript)
        self.assertIn("第 2/4 次发言 · Codex A · 回应", transcript)
        self.assertIn("第 3/4 次发言 · Claude B · 反驳/复核", transcript)
        self.assertIn("第 4/4 次发言 · Codex A · 最终回应", transcript)
        self.assertIn("最终状态：UNRESOLVED", transcript)
        self.assertIn("Codex A 的第一个议题名额：放弃", transcript)
        self.assertNotIn("CONTROL_JSON", transcript)
        self.assertNotIn('"action"', transcript)

    def test_codex_activity_is_derived_from_real_events(self):
        started = MODULE.parse_codex_activity({
            "type": "item.started",
            "item": {"type": "command_execution", "command": "Get-Content analysis-input.json"},
        })
        completed = MODULE.parse_codex_activity({
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "Get-Content analysis-input.json"},
        })
        self.assertIn("读取", started)
        self.assertIn("整理", completed)

    def test_plain_console_keeps_stage_status_and_conversation_as_permanent_text(self):
        stream = io.StringIO()
        console = MODULE.PlainConsole(stream=stream, box_width=48)
        console.set_stage("双方正在独立分析")
        console.set_agent_status("codex", "正在分析")
        console.set_agent_status("codex", "正在分析")
        console.set_agent_status("claude", "正在分析")
        console.utterance("codex", "我不同意这个判断。<CONTROL_JSON>{\"action\":\"ANSWER\"}</CONTROL_JSON>")

        output = stream.getvalue()
        self.assertIn("[阶段] 双方正在独立分析", output)
        self.assertEqual(output.count("Codex A 正在分析……"), 1)
        self.assertIn("Claude B 正在分析……", output)
        self.assertIn("╭", output)
        self.assertIn(" Codex A ", output)
        self.assertIn("│ 我不同意这个判断。", output)
        self.assertIn("╰", output)
        self.assertNotIn("CONTROL_JSON", output)

    def test_boxed_utterance_wraps_chinese_to_equal_display_width(self):
        stream = io.StringIO()
        console = MODULE.PlainConsole(stream=stream, box_width=32)
        console.utterance("claude", "中文发言需要自动换行，同时保留\n\n第二段。")
        box_lines = [line for line in stream.getvalue().splitlines() if line]
        self.assertGreater(len(box_lines), 5)
        self.assertIn(" Claude B ", box_lines[0])
        self.assertTrue(all(MODULE.display_width(line) == 32 for line in box_lines))
        self.assertTrue(any(line == "│" + " " * 30 + "│" for line in box_lines))

    def test_plain_console_accepts_claude_stream_fragments_without_shadowing_method(self):
        output = io.StringIO()
        console = MODULE.PlainConsole(stream=output)
        console.begin("claude", "正在组织回答")
        console.stream("claude", "第一段")
        console.stream("claude", "第二段<CONTROL_JSON>")
        self.assertEqual(console.buffers["claude"], "第一段第二段")

    def test_plain_console_deduplicates_repeated_agent_statuses_within_one_turn(self):
        stream = io.StringIO()
        console = MODULE.PlainConsole(stream=stream)
        console.begin("codex", "正在分析")
        console.set_agent_status("codex", "正在读取材料")
        console.set_agent_status("codex", "材料步骤完成，正在整理判断")
        console.set_agent_status("codex", "正在读取材料")
        console.set_agent_status("codex", "材料步骤完成，正在整理判断")
        self.assertEqual(stream.getvalue().count("正在读取材料"), 1)
        self.assertEqual(stream.getvalue().count("材料步骤完成"), 1)

        console.begin("codex", "正在分析")
        console.set_agent_status("codex", "正在读取材料")
        self.assertEqual(stream.getvalue().count("正在读取材料"), 2)

    def test_plain_console_heartbeat_reports_elapsed_analysis_time(self):
        stream = io.StringIO()
        console = MODULE.PlainConsole(stream=stream)
        console.begin("codex", "正在分析")
        console.heartbeat("codex", 120)
        console.heartbeat("codex", 240)
        output = stream.getvalue()
        self.assertIn("Codex A 仍在分析（已用时 2 分钟）", output)
        self.assertIn("Codex A 仍在分析（已用时 4 分钟）", output)

    def test_plain_console_lists_nominations_and_marks_current_issue(self):
        stream = io.StringIO()
        console = MODULE.PlainConsole(stream=stream)
        discussion = MODULE.empty_discussion()
        first = MODULE.validate_candidate({
            "title": "存量清零还是条件性贬值",
            "opponent_claim": "旧投入已经完全清零",
            "own_position": "旧投入只是条件性减值",
            "evidence_refs": ["DY-1"],
            "material_impact": "player_harm",
        })
        second = MODULE.validate_candidate({
            "title": "资产减值还是承诺错位",
            "opponent_claim": "核心是资产减值",
            "own_position": "核心是承诺错位",
            "evidence_refs": ["DY-2"],
            "material_impact": "event_nature",
        })
        MODULE.apply_nominations(discussion, "codex", [first])
        MODULE.apply_nominations(discussion, "claude", [second])

        console.show_nominations(discussion)
        issue = {
            "id": "A-Q001", "owner": "codex", "title": first["title"],
            "status": "CURRENT", "turn_count": 1,
        }
        console.start_issue(issue)
        console.end_issue({**issue, "status": "RESOLVED"})

        output = stream.getvalue()
        self.assertIn("[提名结果]", output)
        self.assertIn("A1：存量清零还是条件性贬值", output)
        self.assertIn("A2：未提名", output)
        self.assertIn("B1：资产减值还是承诺错位", output)
        self.assertIn("B2：未提名", output)
        self.assertIn("[A1：存量清零还是条件性贬值]", output)
        self.assertIn("提出方：Codex A", output)
        self.assertIn("[A1 结束：已解决]", output)

    def test_plain_console_prints_short_duplicate_withdrawal(self):
        stream = io.StringIO()
        console = MODULE.PlainConsole(stream=stream)
        console.withdraw_candidate(
            {"slot_index": 3, "speaker": "claude"},
            "与 A-Q001 重复，没有必要另开议题",
        )
        self.assertEqual(stream.getvalue().strip(), "B2：与 A1 重复，撤回")

    def test_source_no_longer_uses_rich_dynamic_dashboard(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("from rich.live", source)
        self.assertNotIn("from rich.panel", source)
        self.assertNotIn("from rich.table", source)
        self.assertNotIn("Live(", source)

    def test_claude_thinking_delta_is_not_visible_text(self):
        delta, completed, _ = MODULE.parse_claude_event({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "secret"}},
        })
        self.assertEqual(delta, "")
        self.assertIsNone(completed)

    def test_material_paths_uses_only_contract_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "analysis-input.json").write_text("{}", encoding="utf-8")
            (root / "dashboard.json").write_text("{}", encoding="utf-8")
            self.assertEqual(MODULE.material_paths(root), [root / "analysis-input.json"])

    def test_material_paths_uses_dify_classification_as_semantic_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incoming = root / "incoming"
            incoming.mkdir()
            analysis = root / "analysis-input.json"
            fallback = incoming / "dify-classification.json"
            analysis.write_text("{}", encoding="utf-8")
            fallback.write_text("{}", encoding="utf-8")
            self.assertEqual(MODULE.material_paths(root), [analysis, fallback])

            semantic = root / "semantic-analysis.json"
            semantic.write_text("{}", encoding="utf-8")
            self.assertEqual(MODULE.material_paths(root), [analysis, semantic])

    def test_material_paths_requires_analysis_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(MODULE.WorkflowError):
                MODULE.material_paths(Path(temporary))

    def test_force_archive_moves_whole_current_output_to_run_level_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            output = run_dir / "dual-agent"
            runtime = output / ".runtime"
            runtime.mkdir(parents=True)
            (output / "05-final-analysis.md").write_text("旧终稿", encoding="utf-8")
            (runtime / "sessions.json").write_text("{}", encoding="utf-8")

            archived = MODULE.archive_existing(output)

            self.assertFalse(output.exists())
            self.assertEqual(archived.parent, run_dir / "archive" / "dual-agent")
            self.assertEqual((archived / "05-final-analysis.md").read_text(encoding="utf-8"), "旧终稿")
            self.assertTrue((archived / ".runtime" / "sessions.json").exists())

    def test_claude_command_keeps_session_persistence(self):
        command = MODULE.claude_command("claude", "model", "session-id", resume=False)
        self.assertNotIn("--no-session-persistence", command)
        self.assertIn("--include-partial-messages", command)
        self.assertIn("--session-id", command)
        resumed = MODULE.claude_command("claude", "model", "session-id", resume=True)
        self.assertIn("--resume", resumed)

    def test_codex_completed_message_is_final_content(self):
        delta, completed, session_id = MODULE.parse_codex_event({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "已记住。"},
        })
        self.assertEqual(delta, "已记住。")
        self.assertEqual(completed, "已记住。")
        self.assertIsNone(session_id)

    def test_agent_stdout_log_is_flushed_before_process_finishes(self):
        async def scenario(root: Path) -> None:
            log_prefix = root / "live-agent"
            script = (
                "import json,time; "
                "print(json.dumps({'type':'thread.started','thread_id':'session-test'}),flush=True); "
                "print('LIVE-LINE',flush=True); "
                "time.sleep(0.6); "
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'完成'}}),flush=True)"
            )
            task = asyncio.create_task(MODULE.run_agent_process(
                agent="codex", command=[sys.executable, "-c", script], prompt="测试",
                cwd=root, timeout_seconds=5, log_prefix=log_prefix,
                dashboard=MODULE.PlainConsole(stream=io.StringIO()),
                show_completed_text=False,
            ))
            await asyncio.sleep(0.2)
            live_log = log_prefix.with_suffix(".stdout.log")
            self.assertTrue(live_log.exists())
            self.assertIn("LIVE-LINE", live_log.read_text(encoding="utf-8"))
            result = await task
            self.assertEqual(result.text, "完成")

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_single_jsonl_event_larger_than_default_asyncio_limit_is_supported(self):
        async def scenario(root: Path) -> None:
            large_text_size = 200_000
            script = (
                "import json; "
                f"text='x'*{large_text_size}; "
                "print(json.dumps({'type':'thread.started','thread_id':'large-line'}),flush=True); "
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':text}}),flush=True)"
            )
            result = await MODULE.run_agent_process(
                agent="codex", command=[sys.executable, "-c", script], prompt="测试",
                cwd=root, timeout_seconds=5, log_prefix=root / "large-jsonl-line",
                dashboard=MODULE.PlainConsole(stream=io.StringIO()),
                show_completed_text=False,
            )
            self.assertEqual(len(result.text), large_text_size)

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_stream_reader_failure_is_reported_without_waiting_for_total_timeout(self):
        async def scenario(root: Path) -> None:
            script = (
                "import json; "
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'x'*20000}}),flush=True); "
                "print('process-exited-after-large-line',flush=True)"
            )
            started = asyncio.get_running_loop().time()
            with self.assertRaisesRegex(MODULE.WorkflowError, "CLI stdout 输出读取失败"):
                await MODULE.run_agent_process(
                    agent="codex", command=[sys.executable, "-c", script], prompt="测试",
                    cwd=root, timeout_seconds=20, stream_limit_bytes=1024,
                    log_prefix=root / "reader-failure",
                    dashboard=MODULE.PlainConsole(stream=io.StringIO()),
                    show_completed_text=False,
                )
            self.assertLess(asyncio.get_running_loop().time() - started, 3)

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_analysis_heartbeat_is_emitted_while_agent_is_quiet(self):
        async def scenario(root: Path) -> None:
            stream = io.StringIO()
            script = (
                "import json,time; "
                "print(json.dumps({'type':'thread.started','thread_id':'heartbeat'}),flush=True); "
                "time.sleep(0.35); "
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'完成'}}),flush=True)"
            )
            result = await MODULE.run_agent_process(
                agent="codex", command=[sys.executable, "-c", script], prompt="测试",
                cwd=root, timeout_seconds=5, heartbeat_interval_seconds=0.1,
                log_prefix=root / "heartbeat-agent",
                dashboard=MODULE.PlainConsole(stream=stream), show_completed_text=False,
            )
            self.assertEqual(result.text, "完成")
            self.assertGreaterEqual(stream.getvalue().count("仍在分析"), 2)

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_agent_process_stall_is_stopped_without_waiting_for_total_timeout(self):
        async def scenario(root: Path) -> None:
            script = (
                "import json,time; "
                "print(json.dumps({'type':'thread.started','thread_id':'stalled'}),flush=True); "
                "time.sleep(10)"
            )
            started = asyncio.get_running_loop().time()
            with self.assertRaisesRegex(MODULE.WorkflowError, "连续 .* 秒没有新日志"):
                await MODULE.run_agent_process(
                    agent="codex", command=[sys.executable, "-c", script], prompt="测试",
                    cwd=root, timeout_seconds=20, stall_timeout_seconds=0.2,
                    log_prefix=root / "stalled-agent",
                    dashboard=MODULE.PlainConsole(stream=io.StringIO()),
                    show_completed_text=False,
                )
            self.assertLess(asyncio.get_running_loop().time() - started, 3)

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_stdout_is_monitored_even_when_prompt_delivery_blocks(self):
        async def scenario(root: Path) -> None:
            log_prefix = root / "blocked-prompt"
            script = (
                "import json,time; "
                "print(json.dumps({'type':'thread.started','thread_id':'prompt-block'}),flush=True); "
                "time.sleep(10)"
            )
            with self.assertRaisesRegex(MODULE.WorkflowError, "发送提示超时"):
                await MODULE.run_agent_process(
                    agent="codex", command=[sys.executable, "-c", script],
                    prompt="大" * 5_000_000, cwd=root, timeout_seconds=20,
                    prompt_timeout_seconds=0.2, stall_timeout_seconds=5,
                    log_prefix=log_prefix,
                    dashboard=MODULE.PlainConsole(stream=io.StringIO()),
                    show_completed_text=False,
                )
            self.assertIn(
                "prompt-block",
                log_prefix.with_suffix(".stdout.log").read_text(encoding="utf-8"),
            )

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_large_stream_does_not_starve_stall_watchdog(self):
        async def scenario(root: Path) -> None:
            script = (
                "import json,sys,time; "
                "[sys.stdout.write(json.dumps({'type':'noise','n':i})+'\\n') for i in range(50000)]; "
                "sys.stdout.flush(); time.sleep(10)"
            )
            started = asyncio.get_running_loop().time()
            with self.assertRaisesRegex(MODULE.WorkflowError, "连续 0.2 秒没有新日志"):
                await MODULE.run_agent_process(
                    agent="codex", command=[sys.executable, "-c", script], prompt="测试",
                    cwd=root, timeout_seconds=20, stall_timeout_seconds=0.2,
                    log_prefix=root / "large-stream",
                    dashboard=MODULE.PlainConsole(stream=io.StringIO()),
                    show_completed_text=False,
                )
            self.assertLess(asyncio.get_running_loop().time() - started, 3)

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_claude_events_are_processed_only_after_the_turn_finishes(self):
        async def scenario(root: Path) -> None:
            sessions_path = root / "sessions.json"
            script = (
                "import json,time; "
                "print(json.dumps({'type':'system','session_id':'deferred-session'}),flush=True); "
                "time.sleep(0.6); "
                "print(json.dumps({'type':'result','result':'完整回答','session_id':'deferred-session'}),flush=True)"
            )
            task = asyncio.create_task(MODULE.run_agent_process(
                agent="claude", command=[sys.executable, "-c", script], prompt="测试",
                cwd=root, timeout_seconds=5, stall_timeout_seconds=2,
                log_prefix=root / "deferred-claude",
                dashboard=MODULE.PlainConsole(stream=io.StringIO()),
                sessions_path=sessions_path, show_completed_text=False,
            ))
            await asyncio.sleep(0.2)
            self.assertFalse(sessions_path.exists())
            result = await task
            self.assertEqual(result.text, "完整回答")
            self.assertEqual(result.session_id, "deferred-session")
            self.assertEqual(
                json.loads(sessions_path.read_text(encoding="utf-8"))["claude_session_id"],
                "deferred-session",
            )

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_codex_events_are_processed_only_after_the_turn_finishes(self):
        async def scenario(root: Path) -> None:
            sessions_path = root / "sessions.json"
            script = (
                "import json,time; "
                "print(json.dumps({'type':'thread.started','thread_id':'deferred-codex'}),flush=True); "
                "time.sleep(0.6); "
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'完整回答'}}),flush=True)"
            )
            task = asyncio.create_task(MODULE.run_agent_process(
                agent="codex", command=[sys.executable, "-c", script], prompt="测试",
                cwd=root, timeout_seconds=5, stall_timeout_seconds=None,
                log_prefix=root / "deferred-codex",
                dashboard=MODULE.PlainConsole(stream=io.StringIO()),
                sessions_path=sessions_path, show_completed_text=False,
            ))
            await asyncio.sleep(0.2)
            self.assertFalse(sessions_path.exists())
            result = await task
            self.assertEqual(result.text, "完整回答")
            self.assertEqual(result.session_id, "deferred-codex")

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_log_redaction_masks_query_string_credentials(self):
        redact = getattr(MODULE, "redact_sensitive", lambda value: value)
        source = 'https://example.test/mcp/?tavilyApiKey=secret-value&mode=fast'
        redacted = redact(source)
        self.assertNotIn("secret-value", redacted)
        self.assertIn("tavilyApiKey=***REDACTED***", redacted)

    def test_state_has_one_authoritative_final_and_no_separate_revisions(self):
        state = MODULE.initial_state(Path("E:/demo"), "主题", "gpt", "medium", "deepseek", False)
        self.assertEqual(state["schema_version"], "dual-game-ops-run-5.0")
        self.assertIn("final_report", state["stages"])
        self.assertIn("final_summary", state["stages"])
        self.assertNotIn("codex_revised", state["stages"])
        self.assertNotIn("claude_revised", state["stages"])
        json.dumps(state, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
