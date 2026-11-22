import json
import os
import selectors
import subprocess
import sys
import unittest


class DeadlineTests(unittest.TestCase):
    def test_slow_decision_sends_current_tick_and_continuous_fallback(self):
        script = '''
import time
import mechfight
class Bot:
    def __init__(self, hello): pass
    def act(self, obs):
        if obs["tick"] == 2: time.sleep(.15)
        if obs["tick"] == 4: return {"move": [0, 1], "fire": [True, False]}
        return {"move": [1, 0], "aim": [1, .1], "boost": True,
                "jump": True, "fire": [True, False], "reload": True}
mechfight.run(Bot)
'''
        proc = subprocess.Popen([sys.executable, '-u', '-c', script], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        self.addCleanup(selector.close)
        def send(message):
            proc.stdin.write(json.dumps(message)+'\n'); proc.stdin.flush()
        def receive():
            self.assertTrue(selector.select(timeout=1), 'bot did not reply')
            return json.loads(proc.stdout.readline())
        send({'type':'hello','config':{'bot':{'tick_budget_ms':50}}})
        self.assertEqual(receive()['type'],'ready')
        send({'type':'obs','tick':0})
        self.assertTrue(receive()['fire'][0])
        send({'type':'obs','tick':2})
        self.assertEqual(receive(), {'tick':2,'move':[1,0],'aim':[1,.1],'boost':True})
        send({'type':'obs','tick':4})
        self.assertEqual(receive()['move'],[0,1])
        send({'type':'end'})
        self.assertEqual(proc.wait(timeout=1),0)
        proc.stdin.close(); proc.stdout.close(); proc.stderr.close()


if __name__ == '__main__':
    unittest.main()
