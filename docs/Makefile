# Documentation Makefile

.PHONY: all sphinx clean check-docstrings check-readme

all: sphinx

sphinx:
	@echo "Building Sphinx documentation..."
	cd sphinx && make html
	@echo "Documentation built in sphinx/build/html/"
	@echo "Open sphinx/build/html/index.html to view"

clean:
	@echo "Cleaning documentation build artifacts..."
	cd sphinx && make clean
	@echo "Documentation build artifacts cleaned"

# Check if docstrings are complete
check-docstrings:
	@echo "Checking docstring coverage..."
	python ../scripts/check_docstrings.py ../app -v

# Check if READMEs are complete
check-readme:
	@echo "Checking README documentation..."
	python ../scripts/check_readme.py --path .. --recursive

# Update module READMEs based on template (placeholder for future automation)
update-readmes:
	@echo "This will help standardize module READMEs in the future"
	@echo "For now, manually copy from module_readme_template.md" 