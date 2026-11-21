import unittest

from tools.experiment import compare, factors, interactions


class ExperimentTests(unittest.TestCase):
    def test_factorial_interaction_is_difference_of_differences(self):
        variants = []
        for env in factors(['A=0,1', 'B=0,1']):
            score = int(env['A']) * int(env['B']) * 2
            variants.append({'factors': env, 'matches': [{'seed': 5, 'points': score}, {'seed': 6, 'points': score}]})
        self.assertEqual(interactions(variants)[0]['delta'], 2)
        self.assertEqual(compare(variants[0]['matches'], variants[-1]['matches'])['delta'], 2)

    def test_unpaired_results_are_rejected(self):
        with self.assertRaises(ValueError):
            compare([{'seed': 1, 'points': 1}], [{'seed': 2, 'points': 1}])

    def test_duplicate_factors_are_rejected(self):
        with self.assertRaises(ValueError):
            factors(['A=0,1', 'A=2,3'])
