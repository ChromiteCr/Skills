# SYNTHETIC mathematical fixtures only, not photographs or approved look settings.
# Parameters, seeds, dimensions and tolerances are test choices, NOT confirmed
# photographic recipes. Rebuilt plan 3.4 grain, not historical prototype results.
import json
import math
import unittest
from unittest import mock

import numpy as np
import color_core as c


def reflect(i, n):
    if n == 1:
        return 0
    i %= 2*n-2
    return i if i < n else 2*n-2-i


def scalar_noise(shape, sigma, radius, seed):
    # Independent scalar Gaussian/reflection implementation; no OpenCV or
    # production helper used for expected pixels. Named PCG64 stream is the API.
    rng = np.random.Generator(np.random.PCG64(seed))
    noise = np.array([2*float(rng.random())-1 for _ in range(math.prod(shape))]).reshape(shape)
    weights = [math.exp(-0.5*(i/sigma)**2) for i in range(-radius, radius+1)]
    weights = [w/math.fsum(weights) for w in weights]
    h,w = shape
    result = np.zeros(shape)
    for y in range(h):
        for x in range(w):
            result[y,x] = math.fsum(weights[j+radius]*weights[i+radius]*noise[reflect(y+j,h),reflect(x+i,w)]
                for j in range(-radius,radius+1) for i in range(-radius,radius+1))
    return result


class GrainTests(unittest.TestCase):
    def params(self, **changes):
        # SYNTHETIC TEST PARAMETERS. No confirmation as a photographic preset.
        p = dict(amount=0.4, sigma_fraction=0.1, truncate=2, strength=0.75, seed=19)
        p.update(changes)
        return p

    def apply(self, source, **changes):
        return c.grain_linear_srgb(source, **self.params(**changes))

    def test_planned_grain_api_exists(self):
        self.assertTrue(callable(getattr(c, "grain_linear_srgb", None)))

    def test_scalar_reference_at_edges_and_interior(self):
        source = np.linspace(0.03,0.7,7*9*3).reshape(7,9,3)
        noise = scalar_noise((7,9),0.7,2,19)
        result,qa = self.apply(source)
        np.testing.assert_allclose(result,source*(1+0.3*noise[...,None]),rtol=0,atol=4e-16)
        self.assertEqual(qa["border"], "reflect101")

    def test_one_pixel_hand_calculation(self):
        source = np.array([[[0.25,0.5,0.75]]])
        rng = np.random.Generator(np.random.PCG64(19))
        expected = source*(1+0.3*(2*float(rng.random())-1))
        result,_ = self.apply(source)
        np.testing.assert_allclose(result,expected,rtol=0,atol=3e-16)

    def test_same_seed_same_pixel_and_qa_bytes(self):
        source = np.full((13,17,3),0.4)
        first,q1 = self.apply(source)
        second,q2 = self.apply(source)
        self.assertEqual(first.tobytes(),second.tobytes())
        self.assertEqual(json.dumps(q1,sort_keys=True),json.dumps(q2,sort_keys=True))

    def test_different_seeds_change_texture(self):
        source = np.full((13,17,3),0.4)
        first,_ = self.apply(source)
        second,_ = self.apply(source,seed=20)
        self.assertNotEqual(first.tobytes(),second.tobytes())

    def test_private_rng_leaves_global_state_untouched(self):
        before = np.random.get_state()
        self.apply(np.full((9,13,3),0.4))
        after = np.random.get_state()
        self.assertEqual(before[0],after[0])
        np.testing.assert_array_equal(before[1],after[1])
        self.assertEqual(before[2:],after[2:])

    def test_monochrome_gain_preserves_channel_ratios_and_zero(self):
        source = np.tile([0.1,0.2,0.4],(11,13,1))
        result,_ = self.apply(source)
        np.testing.assert_array_equal(result[...,1],2*result[...,0])
        np.testing.assert_array_equal(result[...,2],4*result[...,0])
        source[...,0]=0
        result,_ = self.apply(source)
        np.testing.assert_array_equal(result[...,0],0)

    def test_no_source_blur_or_channel_mixing(self):
        source = np.zeros((9,13,3))
        source[4,6] = [0.1,0.2,0.4]
        result,_ = self.apply(source)
        np.testing.assert_array_equal(result[source==0],0)
        self.assertTrue(np.all(result[4,6]>0))

    def test_amount_and_strength_linearly_scale_same_noise(self):
        source = np.full((11,13,3),0.4)
        full,_ = self.apply(source,amount=0.8,strength=1)
        half,_ = self.apply(source,amount=0.4,strength=1)
        other,_ = self.apply(source,amount=0.8,strength=0.5)
        np.testing.assert_allclose(half-source,(full-source)/2,rtol=0,atol=8e-17)
        np.testing.assert_array_equal(half,other)

    def test_zero_controls_exact_independent_without_rng_or_backend(self):
        source = np.linspace(0,1,8*9*3).reshape(8,9,3)
        for controls in (dict(amount=0),dict(strength=0)):
            with mock.patch.dict("sys.modules", {"cv2":None}), mock.patch.object(np.random,"Generator",side_effect=AssertionError("RNG used")):
                result,qa = self.apply(source,**controls)
            np.testing.assert_array_equal(result,source)
            self.assertFalse(np.shares_memory(result,source))
            self.assertFalse(qa["noise_performed"])
            self.assertIsNone(qa["opencv_version"])
            self.assertEqual(qa["gain_min"],1)
            self.assertEqual(qa["gain_max"],1)

    def test_black_stays_black_without_rng_or_backend(self):
        with mock.patch.dict("sys.modules", {"cv2":None}), mock.patch.object(np.random,"Generator",side_effect=AssertionError("RNG used")):
            result,qa = self.apply(np.zeros((8,9,3)))
        np.testing.assert_array_equal(result,0)
        self.assertFalse(qa["noise_performed"])
        self.assertEqual(qa["changed_pixels"],0)

    def test_short_side_controls_sigma_and_support(self):
        for shape in ((10,30,3),(30,10,3),(20,60,3)):
            result,qa = self.apply(np.full(shape,0.4))
            self.assertEqual(qa["sigma_pixels"],min(shape[:2])*0.1)
            self.assertEqual(qa["kernel_radius_pixels"],math.ceil(min(shape[:2])*0.2))
            self.assertEqual(result.shape,shape)

    def test_smoothing_correlates_noise_without_normalizing_its_rms(self):
        source = np.full((32,48,3),0.4)
        fine,_ = self.apply(source,sigma_fraction=0.0001,truncate=1)
        coarse,_ = self.apply(source,sigma_fraction=0.06,truncate=3)
        self.assertLess(np.mean(np.abs(np.diff(coarse[...,0],axis=1))),np.mean(np.abs(np.diff(fine[...,0],axis=1))))
        self.assertLess(np.std(coarse),np.std(fine))

    def test_gain_bound_and_highlights_not_clipped(self):
        source = np.ones((17,19,3))
        result,qa = self.apply(source,amount=1,strength=1,sigma_fraction=0.0001,truncate=1)
        self.assertGreater(result.max(),1)
        self.assertGreaterEqual(result.min(),0)
        self.assertLessEqual(result.max(),2)
        self.assertEqual(qa["pixels_above_one"],int(np.count_nonzero(result[...,0]>1)))
        self.assertIn("linear_output_above_one_requires_explicit_tone_handling",qa["warnings"])
        with self.assertRaises(ValueError):
            c.quantize_srgb8(c.linear_to_srgb(result),amplitude_lsb=0,seed=0)

    def test_qa_counts_pixels_once_and_is_stage_scoped(self):
        source = np.full((17,19,3),0.4)
        result,qa = self.apply(source)
        self.assertEqual(qa["pixels_total"],17*19)
        self.assertEqual(qa["changed_pixels"],int(np.count_nonzero(np.any(result!=source,axis=-1))))
        self.assertEqual(qa["brightened_pixels"]+qa["darkened_pixels"],qa["changed_pixels"])
        self.assertNotIn("pass",qa)
        self.assertEqual(qa["seed"],19)
        self.assertEqual(qa["input_space"],"linear-srgb-d65")
        self.assertIn("before_final_output_qa",qa["scope"])
        json.dumps(qa,allow_nan=False)

    def test_noncontiguous_readonly_dtype_and_input_preserved(self):
        source = np.linspace(0,0.7,9*13*3,dtype=np.float32).reshape(9,13,3)
        for view in (source,np.asfortranarray(source),source[::-1,::2],source.transpose(1,0,2)):
            view.setflags(write=False)
            before=view.copy()
            result,_=self.apply(view)
            contiguous,_=self.apply(np.array(view,order="C"))
            self.assertEqual(result.dtype,np.float64)
            np.testing.assert_array_equal(result,contiguous)
            np.testing.assert_array_equal(view,before)
            self.assertFalse(np.shares_memory(result,view))

    def test_invalid_images_rejected_even_disabled(self):
        for value in ([],[0,0,0],np.zeros((2,3)),np.zeros((2,2,4)),np.zeros((1,2,2,3)),np.zeros((0,2,3)),[[[True]*3]],[[["0"]*3]],[[[1j]*3]],[[[None]*3]],[[[float("nan")]*3]],[[[float("inf")]*3]],[[[-1e-20]*3]],[[[np.nextafter(1.,2.)]*3]]):
            with self.subTest(value=str(value)),self.assertRaises(ValueError):
                self.apply(value,strength=0)

    def test_all_parameters_required(self):
        source=np.full((9,13,3),0.4)
        for name in self.params():
            p=self.params(); del p[name]
            with self.subTest(name=name),self.assertRaises(TypeError):
                c.grain_linear_srgb(source,**p)

    def test_invalid_numeric_parameters_even_disabled(self):
        bad_common=(True,np.bool_(True),"0.2",None,[],float("nan"),float("inf"),complex(1))
        bad={"amount":bad_common+(-0.1,1.1),"strength":bad_common+(-0.1,1.1),"sigma_fraction":bad_common+(0,-0.1,1.1),"truncate":bad_common+(0,-1)}
        for name,values in bad.items():
            for value in values:
                with self.subTest(name=name,value=str(value)),self.assertRaises(ValueError):
                    self.apply(np.zeros((9,13,3)),**{name:value})

    def test_seed_validation_and_numpy_integer_acceptance(self):
        for seed in (-1,True,np.bool_(True),1.0,"19",None,[],float("nan")):
            with self.subTest(seed=str(seed)),self.assertRaises(ValueError):
                self.apply(np.zeros((9,13,3)),seed=seed)
        first,_=self.apply(np.full((9,13,3),0.4),seed=np.int64(19))
        second,_=self.apply(np.full((9,13,3),0.4))
        np.testing.assert_array_equal(first,second)
        _,qa=self.apply(np.full((9,13,3),0.4),seed=2**128+3)
        self.assertEqual(qa["seed"],2**128+3)

    def test_support_budget_rejects_without_allocation_or_rng(self):
        for options in (dict(sigma_fraction=1,truncate=2),dict(truncate=1e308)):
            with mock.patch.object(np,"arange",side_effect=AssertionError("allocated")),mock.patch.object(np.random,"Generator",side_effect=AssertionError("RNG used")),self.assertRaises(ValueError):
                self.apply(np.zeros((10,20,3)),**options)

    def test_single_axes_and_tiny_sigma_are_finite(self):
        for shape in ((1,1,3),(1,9,3),(9,1,3)):
            source=np.full(shape,0.4)
            result,_=self.apply(source,sigma_fraction=np.nextafter(0.,1.))
            rng=np.random.Generator(np.random.PCG64(19))
            expected=source*(1+0.3*(2*rng.random(shape[:2])-1)[...,None])
            np.testing.assert_allclose(result,expected,rtol=0,atol=1e-16)
            self.assertTrue(np.all(np.isfinite(result)))

    def test_missing_backend_rejected_without_installation(self):
        with mock.patch.dict("sys.modules", {"cv2":None}),self.assertRaisesRegex(ValueError,"OpenCV"):
            self.apply(np.full((9,13,3),0.4))

    def test_linear_domain_not_implicitly_gamma_decoded(self):
        source=np.full((9,13,3),0.4)
        raw,_=self.apply(source)
        decoded,_=self.apply(c.srgb_to_linear(source))
        np.testing.assert_allclose(raw/source,decoded/c.srgb_to_linear(source),rtol=0,atol=3e-16)
        self.assertFalse(np.allclose(raw,c.linear_to_srgb(decoded)))

    def test_float_pipeline_to_quantization_and_disabled_identity(self):
        codes=np.arange(256,dtype=np.uint8).reshape(16,16)
        source=np.repeat(codes[...,None],3,axis=-1)
        linear=c.srgb_to_linear(source/255)
        disabled,_=self.apply(linear,strength=0)
        np.testing.assert_array_equal(c.quantize_srgb8(c.linear_to_srgb(disabled),amplitude_lsb=0,seed=7),source)
        base=linear*0.4
        first,_=self.apply(base)
        second,_=self.apply(base)
        mapped,qa=c.gamut_map_linear_srgb(first)
        self.assertEqual(qa["pixels_mapped"],0)
        rgb8=c.quantize_srgb8(c.linear_to_srgb(mapped),amplitude_lsb=0.5,seed=7)
        other=c.quantize_srgb8(c.linear_to_srgb(second),amplitude_lsb=0.5,seed=7)
        self.assertEqual(rgb8.tobytes(),other.tobytes())
        self.assertFalse(np.array_equal(first,base))


if __name__ == "__main__":
    unittest.main(verbosity=2)
