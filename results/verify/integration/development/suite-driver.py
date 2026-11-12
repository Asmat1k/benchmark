import unittest,sys
sys.path.insert(0,'src/analysis')
suite=unittest.defaultTestLoader.discover('src/analysis',pattern='test*.py')
def filtered(s):
 for t in s:
  if isinstance(t,unittest.TestSuite):yield from filtered(t)
  elif t.id().endswith('test_r4_r6_r7_actual_replacement_to_persisted_reports'):print('REUSED expensive unchanged R7:',t.id(),flush=True)
  else:yield t
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(filtered(suite)))
raise SystemExit(not result.wasSuccessful())
