"""Independent invariants and exact arithmetic for the limited teaching models."""
from fractions import Fraction
import random
import unittest
from models import apply_layer, quota_period, nearest_rank

class LayerTests(unittest.TestCase):
    def test_lower_is_immutable(self):
        lower={'a':'secret','tree/old':'one'}
        result=apply_layer(lower,{'a':'public'},['tree'])
        self.assertEqual(result,{'a':'public'})
        self.assertEqual(lower,{'a':'secret','tree/old':'one'})
    def test_opaque_hides_only_lower_children(self):
        result=apply_layer({'etc/a':'A','etc/b':'B','outside':'C'},
                           {'etc/new':'N'},opaque_dirs=['etc'])
        self.assertEqual(result,{'outside':'C','etc/new':'N'})
    def test_same_layer_new_file_survives_whiteout(self):
        self.assertEqual(apply_layer({'a':'old'},{'a':'new'},['a']),{'a':'new'})
    def test_subtree_boundary(self):
        self.assertEqual(apply_layer({'dir/a':'A','directory/a':'B'},whiteouts=['dir']),{'directory/a':'B'})
    def test_bad_paths_rejected(self):
        for value in ('/absolute','../out','a/../b','a//b','a/./b',''):
            with self.subTest(value=value),self.assertRaises(ValueError):apply_layer({value:'x'})

class QuotaTests(unittest.TestCase):
    def test_worked_budget(self):
        q=quota_period(100000,100000,4)
        self.assertEqual(q['active_wall_us'],25000)
        self.assertEqual(q['pause_wall_us'],75000)
        self.assertEqual(q['consumed_cpu_us'],100000)
    def test_capacity_below_quota(self):
        q=quota_period(150000,100000,1)
        self.assertEqual(q['pause_wall_us'],0)
        self.assertEqual(q['consumed_cpu_us'],100000)
    def test_conservation_with_exact_rationals(self):
        generator=random.Random(20261101)
        for _ in range(600):
            quota=generator.randint(1,900000);period=generator.randint(1000,200000);parallel=generator.randint(1,16)
            q=quota_period(quota,period,parallel)
            self.assertEqual(q['active_wall_us']+q['pause_wall_us'],period)
            self.assertEqual(q['consumed_cpu_us'],min(Fraction(quota),Fraction(period*parallel)))
            self.assertGreaterEqual(q['pause_wall_us'],0)

class QuantileTests(unittest.TestCase):
    def test_worked_distribution(self):
        data=[5]*9900+[100]*90+[2000]*10
        self.assertEqual(sum(data)/len(data),7.85)
        self.assertEqual(nearest_rank(data,.99),5)
        self.assertEqual(nearest_rank(data,.999),100)
    def test_endpoints_and_repeated_values(self):
        self.assertEqual(nearest_rank([3,1,2],1),3)
        self.assertEqual(nearest_rank([7]*10,.01),7)
    def test_invalid_inputs(self):
        for values,p in [([], .5),([1],0),([1],1.1),([float('nan')],.5)]:
            with self.assertRaises(ValueError):nearest_rank(values,p)

if __name__=='__main__':unittest.main()
