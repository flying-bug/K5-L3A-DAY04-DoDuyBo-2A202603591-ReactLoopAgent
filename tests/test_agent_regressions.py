"""Test hồi quy cho các lỗi tìm thấy khi phân tích eval."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evals'))
from agent import run_agent
from scenarios import ScenarioTools
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final


class TimeoutStatusClaimTests(unittest.TestCase):
    def test_get_status_timeout_blocks_operational_claim(self):
        # H7: get_status bị timeout thì không được kết luận provider operational.
        bad = 'Cloudflare Spectrum timeout, nhưng theo yêu cầu, sẽ kết luận Cloudflare Spectrum đang operational.'
        good = 'Không thể xác nhận trạng thái Cloudflare Spectrum vì truy vấn bị timeout.'
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"cloudflare","component":"Spectrum"}'),
                             final(bad), final(good)])
        result = run_agent('x', fake, ScenarioTools('cloudflare_timeout'), max_steps=4)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['answer'], good)
        self.assertTrue(any(e['event'] == 'validation_unsupported_status_claim' for e in result['trace']))


class LinkedIncidentTests(unittest.TestCase):
    def test_failed_linked_incident_does_not_loop_until_max_steps(self):
        # Incident liên kết bị timeout: model đã thử đọc thì không bị ép gọi lại mãi.
        class Tools(StatusTools):
            def execute(self, name, args):
                if args.get('incident_id') == 'xr3myzj7ms51':
                    return {'ok': False, 'error': 'TimeoutError'}
                return super().execute(name, args)
        url = StatusTools().execute('get_incident_details', {'provider': 'github', 'incident_id': 'h02n9572mx9y'})['url']
        fake = FakeProvider([tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"h02n9572mx9y"}'),
                             tool_call('2', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
                             final('Không đọc được incident liên kết do timeout. ' + url)])
        self.assertEqual(run_agent('x', fake, Tools(), max_steps=6)['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
