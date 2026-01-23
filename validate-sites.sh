#!/bin/bash
# Quick validation script to check sites.csv against rejected_sites.txt
# This can be used locally before committing changes

echo "🔍 Validating sites.csv against rejected_sites.txt..."
echo ""

python check_duplicates.py --validate
exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ Validation passed! Safe to commit."
else
    echo "❌ Validation failed! Please fix violations before committing."
fi

exit $exit_code
