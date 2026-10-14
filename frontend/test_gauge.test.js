"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

// Import helpers from popup.js
const {
    calculateGaugeAngle,
    getScoreStatusLabel,
    GAUGE_CX,
    GAUGE_CY,
    normalizeRiskLevel,
    normalizeDocType,
    countRiskLevels,
} = require("./popup.js");

test("Gauge Geometry: Fixed center coordinates are consistently defined", () => {
    assert.equal(GAUGE_CX, 130);
    assert.equal(GAUGE_CY, 140);
});

test("Gauge Geometry: score-to-angle mapping across key points (0, 25, 50, 55, 75, 100)", () => {
    // Score 0: needle points left (-90 deg from vertical)
    assert.equal(calculateGaugeAngle(0), -90);

    // Score 25: needle points upper-left (-45 deg)
    assert.equal(calculateGaugeAngle(25), -45);

    // Score 50: needle points straight up (0 deg)
    assert.equal(calculateGaugeAngle(50), 0);

    // Score 55: needle points slightly right of vertical (+9 deg)
    assert.equal(calculateGaugeAngle(55), 9);

    // Score 75: needle points upper-right (+45 deg)
    assert.equal(calculateGaugeAngle(75), 45);

    // Score 100: needle points right (+90 deg from vertical)
    assert.equal(calculateGaugeAngle(100), 90);
});

test("Gauge Geometry: needle tip position and constant radius across all angles", () => {
    const NEEDLE_LENGTH = 80; // tip at (0, -80) in local group coordinates
    const testScores = [0, 25, 50, 55, 75, 100];

    for (const score of testScores) {
        const angleDeg = calculateGaugeAngle(score);
        const rad = (angleDeg * Math.PI) / 180;

        // Tip in SVG coordinates: center (130, 140) + rotated vector (0, -80)
        // With angle measured from vertical UP:
        // x_tip = 130 + 80 * sin(angle)
        // y_tip = 140 - 80 * cos(angle)
        const xTip = GAUGE_CX + NEEDLE_LENGTH * Math.sin(rad);
        const yTip = GAUGE_CY - NEEDLE_LENGTH * Math.cos(rad);

        // Distance from pivot (130, 140) must equal exact needle length
        const distance = Math.hypot(xTip - GAUGE_CX, yTip - GAUGE_CY);
        assert.ok(Math.abs(distance - NEEDLE_LENGTH) < 0.0001, `Needle length must stay constant at score ${score}`);

        // Tip must remain safely inside the gauge arc (arc radius R=90, inner edge R=83)
        assert.ok(distance < 83, "Needle tip must remain inside gauge boundaries");
    }

    // Score 0 tip points left
    const angle0 = calculateGaugeAngle(0);
    assert.ok(angle0 === -90);
    const xTip0 = GAUGE_CX + NEEDLE_LENGTH * Math.sin((angle0 * Math.PI) / 180);
    const yTip0 = GAUGE_CY - NEEDLE_LENGTH * Math.cos((angle0 * Math.PI) / 180);
    assert.ok(Math.abs(xTip0 - 50) < 0.001);
    assert.ok(Math.abs(yTip0 - 140) < 0.001);

    // Score 50 tip points straight up
    const angle50 = calculateGaugeAngle(50);
    assert.ok(angle50 === 0);
    const xTip50 = GAUGE_CX + NEEDLE_LENGTH * Math.sin((angle50 * Math.PI) / 180);
    const yTip50 = GAUGE_CY - NEEDLE_LENGTH * Math.cos((angle50 * Math.PI) / 180);
    assert.ok(Math.abs(xTip50 - 130) < 0.001);
    assert.ok(Math.abs(yTip50 - 60) < 0.001);

    // Score 100 tip points right
    const angle100 = calculateGaugeAngle(100);
    assert.ok(angle100 === 90);
    const xTip100 = GAUGE_CX + NEEDLE_LENGTH * Math.sin((angle100 * Math.PI) / 180);
    const yTip100 = GAUGE_CY - NEEDLE_LENGTH * Math.cos((angle100 * Math.PI) / 180);
    assert.ok(Math.abs(xTip100 - 210) < 0.001);
    assert.ok(Math.abs(yTip100 - 140) < 0.001);
});

test("Gauge Geometry: clamping and edge cases", () => {
    // Values below 0 clamp cleanly to -90 deg
    assert.equal(calculateGaugeAngle(-1), -90);
    assert.equal(calculateGaugeAngle(-50), -90);
    assert.equal(calculateGaugeAngle(-999), -90);

    // Values above 100 clamp cleanly to +90 deg
    assert.equal(calculateGaugeAngle(100.5), 90);
    assert.equal(calculateGaugeAngle(150), 90);
    assert.equal(calculateGaugeAngle(999), 90);

    // Non-finite, NaN, null, and invalid strings fallback safely to -90 deg
    assert.equal(calculateGaugeAngle(NaN), -90);
    assert.equal(calculateGaugeAngle(null), -90);
    assert.equal(calculateGaugeAngle(undefined), -90);
    assert.equal(calculateGaugeAngle("not a number"), -90);
});

test("Score Classification: status badge mappings based on application logic", () => {
    // Low risk (< 45) -> GOOD
    assert.equal(getScoreStatusLabel("LOW", 0), "GOOD");
    assert.equal(getScoreStatusLabel("LOW", 25), "GOOD");
    assert.equal(getScoreStatusLabel("LOW", 44), "GOOD");

    // Medium risk (45-80) -> MODERATE
    assert.equal(getScoreStatusLabel("MEDIUM", 45), "MODERATE");
    assert.equal(getScoreStatusLabel("MEDIUM", 50), "MODERATE");
    assert.equal(getScoreStatusLabel("MEDIUM", 55), "MODERATE");
    assert.equal(getScoreStatusLabel("MEDIUM", 78), "MODERATE");
    assert.equal(getScoreStatusLabel("MEDIUM", 80), "MODERATE");

    // High risk (> 80) -> HIGH RISK
    assert.equal(getScoreStatusLabel("HIGH", 85), "HIGH RISK");
    assert.equal(getScoreStatusLabel("HIGH", 100), "HIGH RISK");
    assert.equal(getScoreStatusLabel("CRITICAL", 90), "HIGH RISK");
});

test("Category Breakdown UI Removal: confirmed completely absent from popup.html", () => {
    const htmlPath = path.join(__dirname, "popup.html");
    const html = fs.readFileSync(htmlPath, "utf-8");

    // The score screen must NOT contain any of the removed category items
    assert.equal(html.includes("ATS Essentials"), false, "ATS Essentials must be completely removed");
    assert.equal(html.includes("Tailoring"), false, "Tailoring must be completely removed");
    assert.equal(html.includes("Category Breakdown"), false, "Category Breakdown heading must be completely removed");
    assert.equal(html.includes("cat-score-content"), false, "cat-score-content element must be removed");
    assert.equal(html.includes("cat-score-section"), false, "cat-score-section element must be removed");
    assert.equal(html.includes("cat-score-ats"), false, "cat-score-ats element must be removed");
    assert.equal(html.includes("cat-score-tailoring"), false, "cat-score-tailoring element must be removed");
    assert.equal(html.includes("category-progress-track"), false, "category progress tracks must be removed");
    assert.equal(html.includes("category-progress-fill"), false, "category progress fills must be removed");
});

test("Speedometer UI: verified SVG elements, scale labels, stationary hub, and needle alignment", () => {
    const htmlPath = path.join(__dirname, "popup.html");
    const html = fs.readFileSync(htmlPath, "utf-8");

    // 1. Heading "Your Score" centered
    assert.match(html, /<h2[^>]*class="score-card-heading"[^>]*>Your Score<\/h2>/);

    // 2. SVG gauge with responsive viewBox
    assert.match(html, /<svg[^>]*class="speedometer-svg"[^>]*viewBox="0 0 260 160"/);

    // 3. Smooth multicolor arc progressing from red through orange/yellow to green
    assert.match(html, /id="speedometer-gradient"/);
    assert.match(html, /class="gauge-arc-gradient"/);

    // 4. Subtle outer and inner tracks
    assert.match(html, /class="gauge-track-outer"/);
    assert.match(html, /class="gauge-track-inner"/);

    // 5. Scale labels for 0, 25, 50, 75, 100
    assert.match(html, /class="gauge-scale-label"[^>]*>0<\/text>/);
    assert.match(html, /class="gauge-scale-label"[^>]*>25<\/text>/);
    assert.match(html, /class="gauge-scale-label"[^>]*>50<\/text>/);
    assert.match(html, /class="gauge-scale-label"[^>]*>75<\/text>/);
    assert.match(html, /class="gauge-scale-label"[^>]*>100<\/text>/);

    // 6. Tapered needle group translated to (130, 140)
    assert.match(html, /id="gauge-needle-group"[^>]*transform="translate\(130,\s*140\)\s*rotate\(-90\)"/);
    assert.match(html, /class="gauge-needle-blade"/);

    // 7. Stationary center hub at pivot (130, 140)
    assert.match(html, /class="gauge-center-hub"/);
    assert.match(html, /cx="130"\s+cy="140"/);

    // 8. Numerical score readout and rounded status badge
    assert.match(html, /id="result-risk-score"/);
    assert.match(html, /id="result-risk-level"/);
});

test("CSS Verification: clean speedometer card, needle, and absence of conflicting transform-origin", () => {
    const cssPath = path.join(__dirname, "popup.css");
    const css = fs.readFileSync(cssPath, "utf-8");

    assert.match(css, /\.speedometer-container/);
    assert.match(css, /\.speedometer-svg/);
    assert.match(css, /\.gauge-needle-group/);
    assert.match(css, /\.gauge-needle-blade/);
    assert.match(css, /\.gauge-center-hub|\.gauge-hub-outer/);
    assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);

    // Crucial check: .gauge-needle-group must NOT have CSS transform-origin
    // to avoid overriding SVG user-space pivot calculations
    const needleGroupBlock = css.match(/\.gauge-needle-group\s*\{([^}]*)\}/)?.[1] || "";
    assert.equal(needleGroupBlock.includes("transform-origin"), false, "Must not define conflicting CSS transform-origin");
});

test("Report Features: all existing analysis details, tabs, and clauses preserved", () => {
    const htmlPath = path.join(__dirname, "popup.html");
    const html = fs.readFileSync(htmlPath, "utf-8");

    assert.match(html, /id="btn-reanalyze"/);
    assert.match(html, /id="count-high"/);
    assert.match(html, /id="count-medium"/);
    assert.match(html, /id="count-low"/);
    assert.match(html, /id="tab-high"/);
    assert.match(html, /id="tab-medium"/);
    assert.match(html, /id="tab-low"/);
    assert.match(html, /id="clause-category-heading"/);
    assert.match(html, /id="clause-panel"/);
    assert.match(html, /id="result-doc-context"/);
});
