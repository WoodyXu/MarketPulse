import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM_ROOT = REPO_ROOT / "miniprogram"
COMMON_PHONE_WIDTHS_PX = (320, 390)


def read_miniprogram_file(*parts):
    return (MINIPROGRAM_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def extract_rpx_value(css, selector, property_name):
    match = re.search(
        rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\}}",
        css,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError(f"missing selector: {selector}")

    property_match = re.search(
        rf"{re.escape(property_name)}\s*:\s*([0-9]+)rpx",
        match.group("body"),
    )
    if not property_match:
        raise AssertionError(f"missing {property_name} in {selector}")
    return int(property_match.group(1))


def extract_horizontal_padding_rpx(css, selector):
    match = re.search(
        rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\}}",
        css,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError(f"missing selector: {selector}")

    property_match = re.search(
        r"padding\s*:\s*([^;]+)",
        match.group("body"),
    )
    if not property_match:
        raise AssertionError(f"missing padding in {selector}")

    values = [
        int(value)
        for value in re.findall(r"([0-9]+)rpx", property_match.group(1))
    ]
    if len(values) == 1:
        return values[0]
    if len(values) in (2, 3, 4):
        return values[1]
    raise AssertionError(f"unsupported padding shorthand in {selector}")


def rpx_to_px(value, viewport_width_px):
    return value * viewport_width_px / 750


class MiniProgramMobileCompatibilityTest(unittest.TestCase):
    def test_common_phone_widths_keep_panels_and_charts_readable(self):
        app_wxss = read_miniprogram_file("app.wxss")
        ashare_wxss = read_miniprogram_file("pages", "ashare", "index.wxss")
        beijing_wxss = read_miniprogram_file("pages", "beijing", "index.wxss")

        page_padding_rpx = extract_horizontal_padding_rpx(app_wxss, ".page")
        panel_padding_rpx = extract_horizontal_padding_rpx(app_wxss, ".panel")
        chart_height_rpx = extract_rpx_value(ashare_wxss, ".chart-box", "height")

        self.assertIn("overflow-x: hidden", app_wxss)
        self.assertIn("box-sizing: border-box", app_wxss)
        self.assertEqual(
            chart_height_rpx,
            extract_rpx_value(beijing_wxss, ".chart-box", "height"),
        )

        for viewport_width_px in COMMON_PHONE_WIDTHS_PX:
            horizontal_inset_px = rpx_to_px(
                2 * page_padding_rpx + 2 * panel_padding_rpx,
                viewport_width_px,
            )
            panel_content_width_px = viewport_width_px - horizontal_inset_px
            chart_height_px = rpx_to_px(chart_height_rpx, viewport_width_px)

            self.assertGreaterEqual(panel_content_width_px, 270)
            self.assertGreaterEqual(chart_height_px, 220)
            self.assertLess(chart_height_px, viewport_width_px)

    def test_tabs_and_credit_sub_tabs_are_horizontally_scrollable(self):
        ashare_wxml = read_miniprogram_file("pages", "ashare", "index.wxml")
        beijing_wxml = read_miniprogram_file("pages", "beijing", "index.wxml")
        ashare_wxss = read_miniprogram_file("pages", "ashare", "index.wxss")
        beijing_wxss = read_miniprogram_file("pages", "beijing", "index.wxss")

        for wxml in (ashare_wxml, beijing_wxml):
            self.assertRegex(
                wxml,
                r'class="tabs"[^>]*scroll-x="true"[^>]*show-scrollbar="false"',
            )

        self.assertRegex(
            beijing_wxml,
            r'class="sub-tabs"[^>]*scroll-x="true"[^>]*show-scrollbar="false"',
        )
        self.assertIn("white-space: nowrap", ashare_wxss)
        self.assertGreaterEqual(beijing_wxss.count("white-space: nowrap"), 2)

    def test_top_stock_table_can_reach_every_column_on_phone_widths(self):
        app_wxss = read_miniprogram_file("app.wxss")
        ashare_wxml = read_miniprogram_file("pages", "ashare", "index.wxml")
        ashare_wxss = read_miniprogram_file("pages", "ashare", "index.wxss")

        page_padding_rpx = extract_horizontal_padding_rpx(app_wxss, ".page")
        panel_padding_rpx = extract_horizontal_padding_rpx(app_wxss, ".panel")
        table_min_width_rpx = extract_rpx_value(
            ashare_wxss,
            ".stock-table",
            "min-width",
        )

        self.assertRegex(
            ashare_wxml,
            r'class="stock-table-scroll"[^>]*scroll-x="true"'
            r'[^>]*show-scrollbar="false"',
        )
        self.assertIn("max-width: 100%", ashare_wxss)

        for viewport_width_px in COMMON_PHONE_WIDTHS_PX:
            visible_width_px = viewport_width_px - rpx_to_px(
                2 * page_padding_rpx + 2 * panel_padding_rpx,
                viewport_width_px,
            )
            table_width_px = rpx_to_px(table_min_width_rpx, viewport_width_px)
            self.assertGreater(table_width_px, visible_width_px)

    def test_loading_error_and_empty_states_remain_in_normal_layout(self):
        for page_name in ("ashare", "beijing"):
            wxml = read_miniprogram_file("pages", page_name, "index.wxml")
            wxss = read_miniprogram_file("pages", page_name, "index.wxss")

            self.assertIn('wx:if="{{activeSectionState.loading}}"', wxml)
            self.assertIn('class="loading-state"', wxml)
            self.assertIn('wx:if="{{activeSectionState.error}}"', wxml)
            self.assertIn('class="error-state"', wxml)
            self.assertIn('bindtap="retryActiveSection"', wxml)
            self.assertIn("min-height: 96rpx", wxss)
            self.assertNotIn("position: absolute", wxss)
            self.assertNotIn("position: fixed", wxss)

    def test_home_entries_reserve_space_for_navigation_arrow(self):
        home_wxss = read_miniprogram_file("pages", "home", "index.wxss")
        right_padding_rpx = extract_rpx_value(
            home_wxss,
            ".board-entry",
            "padding-right",
        )

        self.assertGreaterEqual(right_padding_rpx, 64)

    def test_ec_canvas_fills_bounded_chart_container(self):
        component_wxss = read_miniprogram_file(
            "components",
            "ec-canvas",
            "ec-canvas.wxss",
        )
        for page_name in ("ashare", "beijing"):
            wxss = read_miniprogram_file("pages", page_name, "index.wxss")
            self.assertIn("overflow: hidden", wxss)
            self.assertIn("min-width: 0", wxss)

        self.assertIn("width: 100%", component_wxss)
        self.assertIn("height: 100%", component_wxss)


if __name__ == "__main__":
    unittest.main()
