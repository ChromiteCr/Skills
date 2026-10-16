# SYNTHETIC mathematical fixtures only, not real photos or approved look recipes.
# All sizes, tint vectors and creative parameters below are unconfirmed TEST inputs.
import inspect
import json
import math
import unittest
from unittest import mock
import numpy as np
import color_core as core

PARAMS = dict(threshold=0.5, sigma_fraction=0.125, truncate=2.0,
              strength=0.5, tint_linear_rgb=[1.0, 0.0, 0.25])
Y_WEIGHTS = (87098/409605, 175762/245763, 12673/175545)


def reference(rgb, **params):
    # Independent scalar, explicit 2D convolution. No OpenCV or core helpers.
    h, w, _ = rgb.shape
    sigma = min(h,w)*params["sigma_fraction"]
    radius = max(1, math.ceil(sigma*params["truncate"]))
    offsets = list(range(-radius,radius+1))
    weights = [math.exp(-0.5*(v/sigma)**2) for v in offsets]
    norm = math.fsum(weights)
    weights = [v/norm for v in weights]
    source = [[max(0, math.fsum(float(rgb[y,x,c])*Y_WEIGHTS[c]
                   for c in range(3))-params["threshold"]) for x in range(w)] for y in range(h)]
    def mirror(i,n):
        if n == 1:
            return 0
        j = i % (2*n-2)
        return j if j<n else 2*n-2-j
    out = rgb.copy()
    for y in range(h):
        for x in range(w):
            blurred = math.fsum(weights[j]*weights[i]*source[mirror(y+dy,h)][mirror(x+dx,w)]
                for j,dy in enumerate(offsets) for i,dx in enumerate(offsets))
            halo = max(0,blurred-source[y][x])
            for c in range(3):
                out[y,x,c] += params["strength"]*halo*params["tint_linear_rgb"][c]
    return out


class HalationTests(unittest.TestCase):
    def halo(self,rgb,**changes):
        return core.halation_linear_srgb(rgb, **(PARAMS | changes))

    def impulse(self):
        rgb = np.zeros((9,11,3)); rgb[4,5] = 1
        return rgb

    def test_planned_halation_api_exists(self):
        self.assertTrue(callable(getattr(core,"halation_linear_srgb",None)))

    def test_impulse_scalar_reference_and_uncolored_core(self):
        rgb = self.impulse()
        out,qa = self.halo(rgb)
        np.testing.assert_allclose(out,reference(rgb,**PARAMS),rtol=3e-15,atol=2e-16)
        np.testing.assert_array_equal(out[4,5],rgb[4,5])
        self.assertGreater(out[4,6,0],0)
        self.assertEqual(qa["highlight_pixels"],1)

    def test_hand_computed_neighbor_and_explicit_tint(self):
        rgb = np.zeros((8,8,3)); rgb[4,4] = 1
        out,_ = self.halo(rgb)
        normalizer = 1+2*math.exp(-0.5)+2*math.exp(-2)
        neighbor = 0.5*0.5*math.exp(-0.5)/normalizer**2
        np.testing.assert_allclose(out[4,5],neighbor*np.array([1,0,0.25]),rtol=3e-15,atol=0)
        np.testing.assert_array_equal(out[...,1],rgb[...,1])

    def test_colored_edge_matches_scalar_and_rgb_order(self):
        rgb = np.arange(60,dtype=float).reshape(4,5,3)/59
        params = PARAMS | dict(threshold=0.1,sigma_fraction=0.2,tint_linear_rgb=[0,0.25,1])
        out,_ = core.halation_linear_srgb(rgb,**params)
        np.testing.assert_allclose(out,reference(rgb,**params),rtol=4e-15,atol=3e-16)
        np.testing.assert_array_equal(out[...,0],rgb[...,0])

    def test_uniform_fields_are_exact_identity_without_backend(self):
        with mock.patch.dict("sys.modules",{"cv2":None}):
            for color in ([0,0,0],[1,1,1],[0.75]*3,[0.9,0.8,0.6]):
                rgb = np.tile(color,(7,8,1))
                out,qa = self.halo(rgb)
                np.testing.assert_array_equal(out,rgb)
                self.assertFalse(qa["blur_performed"])
                self.assertFalse(np.shares_memory(out,rgb))

    def test_zero_strength_and_zero_tint_exact_no_backend(self):
        rgb = self.impulse()
        with mock.patch.dict("sys.modules",{"cv2":None}):
            for options in (dict(strength=0),dict(tint_linear_rgb=[0,0,0])):
                out,qa = self.halo(rgb,**options)
                np.testing.assert_array_equal(out,rgb)
                self.assertFalse(qa["blur_performed"])
                self.assertEqual(qa["changed_pixels"],0)

    def test_no_highlights_including_threshold_are_reported(self):
        rgb = np.zeros((4,5,3)); rgb[1,2] = 0.5
        out,qa = self.halo(rgb)
        np.testing.assert_array_equal(out,rgb)
        self.assertEqual(qa["highlight_pixels"],0)
        self.assertIn("no_highlights_above_threshold",qa["warnings"])
        out,_ = self.halo(self.impulse(),threshold=1)
        np.testing.assert_array_equal(out,self.impulse())

    def test_short_side_sigma_and_support(self):
        for shape,sigma,radius in (((8,20,3),1,2),((20,8,3),1,2),((16,40,3),2,4)):
            rgb = np.zeros(shape); rgb[shape[0]//2,shape[1]//2]=1
            _,qa = self.halo(rgb)
            self.assertEqual(qa["sigma_pixels"],sigma)
            self.assertEqual(qa["kernel_radius_pixels"],radius)
            self.assertEqual(qa["border"],"reflect101")

    def test_finite_support_never_wraps(self):
        rgb = np.zeros((16,20,3)); rgb[8,0]=1
        out,_ = self.halo(rgb,sigma_fraction=1/16,truncate=2)
        np.testing.assert_array_equal(out[:,3:],rgb[:,3:])
        np.testing.assert_array_equal(out[:6],rgb[:6])
        np.testing.assert_array_equal(out[11:],rgb[11:])
        self.assertGreater(out[8,1,0],0)

    def test_reflect_boundary_matches_scalar(self):
        rgb = np.zeros((4,5,3)); rgb[0,0]=1; rgb[3,4]=0.75
        out,_ = self.halo(rgb)
        np.testing.assert_allclose(out,reference(rgb,**PARAMS),rtol=3e-15,atol=2e-16)

    def test_strength_is_linear_and_additive(self):
        rgb = self.impulse()
        full,_ = self.halo(rgb,strength=1)
        half,_ = self.halo(rgb,strength=0.5)
        np.testing.assert_allclose(half-rgb,(full-rgb)/2,rtol=0,atol=2e-16)
        self.assertTrue(np.all(full>=half)); self.assertTrue(np.all(half>=rgb))

    def test_selection_uses_linear_luminance(self):
        rgb = np.zeros((8,8,3)); rgb[4,4]=[1,0,0]
        red,qa = self.halo(rgb,threshold=0.25)
        self.assertEqual(qa["highlight_pixels"],0)
        np.testing.assert_array_equal(red,rgb)
        rgb[4,4]=[0,1,0]
        green,qa = self.halo(rgb,threshold=0.25)
        self.assertEqual(qa["highlight_pixels"],1)
        self.assertGreater(green[4,5,0],0)

    def test_overrange_preserved_and_counted_per_pixel(self):
        rgb = np.zeros((9,9,3)); rgb[4,4]=1; rgb[4,5]=[1,0,0]
        out,qa = self.halo(rgb,strength=1)
        self.assertGreater(out[4,5,0],1)
        self.assertEqual(qa["pixels_above_one"],int(np.count_nonzero(np.any(out>1,axis=-1))))
        self.assertIn("linear_output_above_one_requires_explicit_tone_handling",qa["warnings"])
        self.assertNotIn("pass",qa)

    def test_readonly_noncontiguous_input_preserved(self):
        rgb = self.impulse()
        for view in (np.asfortranarray(rgb),rgb[:,::-1],rgb.transpose(1,0,2)):
            view.setflags(write=False); before=view.copy()
            out,_ = self.halo(view)
            expected,_ = self.halo(np.array(view,order="C"))
            np.testing.assert_array_equal(out,expected)
            np.testing.assert_array_equal(view,before)
            self.assertEqual(out.dtype,np.float64)
            self.assertFalse(np.shares_memory(out,view))

    def test_parameters_required_and_strict_even_disabled(self):
        signature=inspect.signature(core.halation_linear_srgb)
        for name in PARAMS:
            self.assertIs(signature.parameters[name].default,inspect.Parameter.empty)
        for name in ("threshold","sigma_fraction","truncate","strength"):
            for bad in (True,"0.5",None,float("nan"),float("inf"),-0.1):
                with self.subTest(name=name,bad=bad),self.assertRaises(ValueError):
                    self.halo(self.impulse(),**{name:bad})
        for name in ("threshold","sigma_fraction","strength"):
            with self.assertRaises(ValueError): self.halo(self.impulse(),**{name:1.1})
        for name in ("sigma_fraction","truncate"):
            with self.assertRaises(ValueError): self.halo(self.impulse(),**{name:0})
        with self.assertRaises(ValueError): self.halo(self.impulse(),threshold=-1,strength=0)

    def test_tint_exact_shape_finite_bounded_no_broadcast(self):
        for tint in (1,[],[1,0],[[1,0,0]],[True,False,False],["1","0","0"],
                     [1j,0,0],[float("nan"),0,0],[float("inf"),0,0],[-0.1,0,0],[1.1,0,0]):
            with self.subTest(tint=tint),self.assertRaises(ValueError):
                self.halo(self.impulse(),tint_linear_rgb=tint,strength=0)

    def test_invalid_images_rejected(self):
        for rgb in ([],[0,0,0],np.zeros((3,3)),np.zeros((0,3,3)),np.zeros((2,2,4)),
                    np.zeros((1,2,2,3)),[[[True]*3]],[[["0"]*3]],[[[1j]*3]],
                    [[[float("nan")]*3]],[[[float("inf")]*3]],[[[-1e-20]*3]],
                    [[[1.0000000000000002]*3]]):
            with self.subTest(shape=np.shape(rgb)),self.assertRaises(ValueError):
                self.halo(rgb)

    def test_support_budget_rejected_before_allocation(self):
        for params in (dict(sigma_fraction=1,truncate=2),dict(truncate=1e308)):
            with self.assertRaises(ValueError): self.halo(self.impulse(),strength=0,**params)

    def test_single_axes_and_subnormal_sigma(self):
        for shape in ((1,5,3),(5,1,3)):
            rgb=np.zeros(shape); rgb.reshape(-1,3)[2]=1
            out,_=self.halo(rgb,sigma_fraction=0.5,truncate=1)
            params=PARAMS | dict(sigma_fraction=0.5,truncate=1)
            np.testing.assert_allclose(out,reference(rgb,**params),rtol=3e-15,atol=2e-16)
        rgb=self.impulse()
        out,_=self.halo(rgb,sigma_fraction=np.nextafter(0.,1.))
        np.testing.assert_array_equal(out,rgb)

    def test_repeatability_json_and_rng_unchanged(self):
        rgb=self.impulse(); state=np.random.get_state()
        first,q1=self.halo(rgb); second,q2=self.halo(rgb)
        self.assertEqual(first.tobytes(),second.tobytes())
        self.assertEqual(json.dumps(q1,sort_keys=True),json.dumps(q2,sort_keys=True))
        after=np.random.get_state()
        self.assertEqual(state[0],after[0]); np.testing.assert_array_equal(state[1],after[1])
        self.assertEqual(state[2:],after[2:])
        self.assertEqual(q1["pixels_total"],99)
        self.assertEqual(q1["changed_pixels"],int(np.count_nonzero(np.any(first!=rgb,axis=-1))))
        self.assertEqual(q1["tint_linear_rgb"],PARAMS["tint_linear_rgb"])

    def test_missing_backend_fails_without_installation(self):
        with mock.patch.dict("sys.modules",{"cv2":None}):
            with self.assertRaisesRegex(ValueError,"OpenCV is required"):
                self.halo(self.impulse())

    def test_encoded_input_is_not_silently_decoded(self):
        encoded=np.zeros((8,8,3)); encoded[4,4]=0.75
        proper,_=self.halo(core.srgb_to_linear(encoded),threshold=0.25)
        wrong,_=self.halo(encoded,threshold=0.25)
        self.assertGreater(float(np.max(np.abs(proper-wrong))),0.1)

    def test_existing_float_path_to_final_quantization(self):
        source=np.zeros((9,9,3),dtype=np.uint8); source[4,4]=(180,190,200)
        linear=core.srgb_to_linear(source.astype(float)/255)
        bloomed,_=core.bloom_linear_srgb(linear,threshold=0.25,sigma_fraction=0.1,
                                         truncate=2,strength=0.1)
        halo,qa=self.halo(bloomed,threshold=0.25,strength=0.25)
        self.assertEqual(qa["pixels_above_one"],0)
        mapped,_=core.gamut_map_linear_srgb(halo)
        encoded=core.linear_to_srgb(mapped)
        out=core.quantize_srgb8(encoded,amplitude_lsb=0,seed=0)
        self.assertEqual(out.shape,source.shape)
        self.assertTrue(np.any(out[3:6,3:6,0]>source[3:6,3:6,0]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
