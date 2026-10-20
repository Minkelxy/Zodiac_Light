"""Reject inward, partial, resized or otherwise unrequested mousebite edits."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('depanel_standard',Path(__file__).resolve().parents[1]/'hardware/nfc-talisman/scripts/check_standard_delivery.py')
CHECK=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class DepanelDisplacementTests(unittest.TestCase):
    def setUp(self):
        self.before={}
        for group in range(5):
            for edge in 'NSEW':
                for index in range(1,6):
                    ident=f'G{group}_{edge}_MB{index}'
                    self.before[('PAD',ident)]=dict(num=ident,plated=False,layerId=12,
                        centerX=1000+group*100,centerY=2000+index*30,hole=dict(width=.4/.0254,height=.4/.0254),netName='')
        self.current=copy.deepcopy(self.before)
        for body in self.current.values():
            dx,dy=CHECK._mousebite_delta(body)
            body['centerX']=round(body['centerX']+dx/.0254,4)
            body['centerY']=round(body['centerY']+dy/.0254,4)

    def test_exact_outward_shift_is_accepted_without_mutating_input(self):
        snapshot=copy.deepcopy(self.current)
        self.assertEqual(CHECK._undo_mousebites(self.before,self.current),self.before)
        self.assertEqual(self.current,snapshot)

    def test_wrong_direction_or_distance_is_rejected(self):
        key=('PAD','G0_N_MB1')
        for offset in (-.4,.3,.5):
            with self.subTest(offset=offset):
                self.current[key]['centerY']=self.before[key]['centerY']+offset/.0254
                with self.assertRaisesRegex(ValueError,'exactly 0.40 mm outward'):
                    CHECK._undo_mousebites(self.before,self.current)

    def test_missing_hole_is_rejected(self):
        del self.current[('PAD','G0_N_MB1')]
        with self.assertRaisesRegex(ValueError,'100 owned mousebites'):
            CHECK._undo_mousebites(self.before,self.current)

    def test_resized_hole_is_rejected(self):
        self.current[('PAD','G0_N_MB1')]['hole']['width']=.5/.0254
        with self.assertRaisesRegex(ValueError,'diameter/plating'):
            CHECK._undo_mousebites(self.before,self.current)

    def test_unrequested_star_hole_and_properties_remain_protected(self):
        star=('PAD','star')
        self.before[star]=dict(num='HIP123',centerX=50,centerY=60,plated=False,hole=dict(width=.8/.0254))
        self.current[star]=dict(self.before[star],centerX=51)
        self.assertNotEqual(CHECK._undo_mousebites(self.before,self.current),self.before)
        self.current[('PAD','G0_N_MB1')]['netName']='unexpected'
        self.assertEqual(CHECK._undo_mousebites(self.before,self.current)[('PAD','G0_N_MB1')]['netName'],'unexpected')


class DepanelGerberTests(unittest.TestCase):
    def program(self,diameter='0.6',pad='G01X10000000Y20000000D03*'):
        return ('%FSLAX36Y36*%\n%MOMM*%\n%ADD10C,'+diameter+'*%\nG04 Pad Start*\nD10*\n'+pad+
                '\nG04 Pad End*\nG04 Track Start*\nD10*\nG01X10000000Y20000000D03*\nG04 Track End*\n').encode()

    def test_only_the_exact_named_pad_flash_is_relocated(self):
        commands=CHECK._gerber_commands(self.program(),mousebite_moves=[((10,20),(10,20.4))])
        self.assertIn('G01X10000000Y20400000D03*',commands)
        self.assertIn('G01X10000000Y20000000D03*',commands)
        self.assertEqual(commands.count('G01X10000000Y20400000D03*'),1)

    def test_nearby_unrequested_coordinate_is_not_rewritten(self):
        commands=CHECK._gerber_commands(self.program(pad='G01X10001000Y20000000D03*'),mousebite_moves=[((10,20),(10,20.4))])
        self.assertIn('G01X10001000Y20000000D03*',commands)
        self.assertNotIn('G01X10000000Y20400000D03*',commands)

    def test_aperture_changes_remain_visible(self):
        moves=[((10,20),(10,20.4))]
        self.assertNotEqual(CHECK._gerber_commands(self.program(),mousebite_moves=moves),
                            CHECK._gerber_commands(self.program(diameter='0.8'),mousebite_moves=moves))


if __name__=='__main__':
    unittest.main()
