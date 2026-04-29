#!/bin/bash
#
# Quick test del nuevo sistema de TP optimizable
#

echo "================================================================================"
echo "🧪 TESTING TP DISTRIBUTION OPTIMIZATION"
echo "================================================================================"
echo ""

# Test 1: Balanced preset
echo "Test 1: Balanced preset (33/33/33)"
bash run_dual_validation.sh --quick --tp-preset balanced 2>&1 | tail -20

echo ""
echo "================================================================================"
echo "✅ Test completed! Check outputs/walk_forward_results.json for TP percentages"
echo "================================================================================"
