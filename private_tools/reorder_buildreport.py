#!/usr/bin/env python3
"""
BuildReport Module Reordering Tool

This script reads two build reports and reorders the driver modules in the second
report based on the order found in the first report.

Usage:
    python reorder_buildreport.py <report1> <report2>

Output:
    BuildReport-reorder_driver.txt (modules reordered only)
    BuildReport-reorder_driver_and_lib.txt (modules and libraries reordered)
"""

import sys
import re
from pathlib import Path


class BuildReport:
    """Represents a build report with header and modules."""
    
    MODULE_SEPARATOR = ">======================================================================================================================================================================================================<"
    MODULE_HEADER = "Module Summary"
    
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.header = ""
        self.modules = {}  # dict: module_name -> module_content
        self.module_order = []  # list of module names in order
        self._parse()
    
    def _parse(self):
        """Parse the build report file."""
        with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Find the first module section
        pattern = f"{re.escape(self.MODULE_SEPARATOR)}\n{re.escape(self.MODULE_HEADER)}"
        match = re.search(pattern, content)
        
        if not match:
            raise ValueError(f"No modules found in {self.filepath}")
        
        # Extract header (everything before first module)
        first_module_start = match.start()
        self.header = content[:first_module_start].rstrip('\n')
        
        # Extract modules
        modules_section = content[first_module_start:]
        
        # Find all module start positions
        separator_pattern = re.escape(self.MODULE_SEPARATOR) + r'\n' + re.escape(self.MODULE_HEADER)
        module_starts = []
        for match in re.finditer(separator_pattern, modules_section):
            module_starts.append(match.start())
        
        # Extract each module block
        module_name_count = {}  # Track duplicate module names
        for i, start_pos in enumerate(module_starts):
            if i + 1 < len(module_starts):
                end_pos = module_starts[i + 1]
            else:
                end_pos = len(modules_section)
            
            block = modules_section[start_pos:end_pos]
            
            # Extract module name
            module_name = self._extract_module_name(block)
            if module_name:
                # Handle duplicate module names by adding index
                if module_name in module_name_count:
                    module_name_count[module_name] += 1
                    unique_key = f"{module_name}#{module_name_count[module_name]}"
                else:
                    module_name_count[module_name] = 1
                    unique_key = module_name
                
                self.modules[unique_key] = block
                self.module_order.append(unique_key)
        
        print(f"Parsed {self.filepath.name}: {len(self.modules)} modules found")
    
    def _extract_module_name(self, module_block):
        """Extract the module name from a module block."""
        # Look for "Module Name: <name>"
        match = re.search(r'Module Name:\s+(\S+)', module_block)
        if match:
            return match.group(1)
        return None
    
    def reorder_modules(self, reference_order):
        """
        Reorder modules based on a reference order.
        
        Args:
            reference_order: List of module names in desired order
            
        Returns:
            New ordered list of module names
        """
        # Create new order based on reference
        new_order = []
        used_modules = set()
        
        # Add modules in reference order if they exist
        for module_name in reference_order:
            if module_name in self.modules:
                new_order.append(module_name)
                used_modules.add(module_name)
        
        # Add any remaining modules not in reference (at the end)
        for module_name in self.module_order:
            if module_name not in used_modules:
                new_order.append(module_name)
        
        self.module_order = new_order
        return new_order
    
    def save(self, output_path, reorder_libraries=False, reference_report=None):
        """Save the build report to a file."""
        output_path = Path(output_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write(self.header)
            f.write('\n')
            
            # Write modules in order
            total = len(self.module_order)
            for idx, module_name in enumerate(self.module_order, 1):
                if reorder_libraries and idx % 50 == 0:
                    print(f"  Processing module {idx}/{total}...")
                
                f.write('\n')
                module_content = self.modules[module_name]
                
                if reorder_libraries and reference_report:
                    # Reorder libraries within this module
                    module_content = self._reorder_libraries_in_module(
                        module_content, 
                        module_name, 
                        reference_report
                    )
                
                f.write(module_content)
        
        print(f"Saved reordered report to {output_path}")
    
    def get_library_count(self, module_name):
        """Get the number of libraries in a specific module."""
        if module_name not in self.modules:
            return 0
        
        module_content = self.modules[module_name]
        lib_section_marker = ">------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------<\nLibrary\n--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------"
        lib_section_end = "<------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------>"
        
        if lib_section_marker not in module_content or lib_section_end not in module_content:
            return 0
        
        parts = module_content.split(lib_section_marker, 1)
        if len(parts) != 2:
            return 0
        
        remaining = parts[1]
        lib_parts = remaining.split(lib_section_end, 1)
        if len(lib_parts) < 1:
            return 0
        
        lib_section = lib_parts[0]
        # Pattern updated to handle multi-line library info (same as in _reorder_libraries_in_module)
        lib_pattern = re.compile(r'^([^\n]+\.inf)\n(\{[^}]+\})', re.MULTILINE)
        
        return len(lib_pattern.findall(lib_section))
    
    def _reorder_libraries_in_module(self, module_content, module_name, reference_report):
        """Reorder libraries within a module based on reference report."""
        # Find the library section header
        lib_section_marker = ">------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------<\nLibrary\n--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------"
        lib_section_end = "<------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------>"
        
        if lib_section_marker not in module_content or lib_section_end not in module_content:
            return module_content
        
        # Split into: before_lib_section, lib_section, after_lib_section
        parts = module_content.split(lib_section_marker, 1)
        if len(parts) != 2:
            return module_content
        
        before_lib_section = parts[0]
        remaining = parts[1]
        
        # Split lib section and what comes after
        lib_parts = remaining.split(lib_section_end, 1)
        if len(lib_parts) != 2:
            return module_content
        
        lib_section = lib_parts[0]
        after_lib_section = lib_parts[1]
        
        # Pattern: .inf line followed by {LibName: ...} line (which may span multiple lines)
        # The library info starts with { and ends with }, and may continue on the next line if indented with a space
        lib_pattern = re.compile(r'^([^\n]+\.inf)\n(\{[^}]+\})', re.MULTILINE)
        
        # Extract all libraries from current module (preserve original order)
        current_libs = []
        for match in lib_pattern.finditer(lib_section):
            lib_path = match.group(1)
            lib_info = match.group(2)
            lib_name = self._extract_library_name(lib_info)
            
            # Normalize path for comparison
            normalized_path = lib_path.replace('\\', '/').lower()
            
            current_libs.append({
                'path': lib_path,
                'normalized_path': normalized_path,
                'name': lib_name,
                'info': lib_info,
                'full': f"{lib_path}\n{lib_info}"
            })
        
        if not current_libs:
            return module_content
        
        # Get reference library order from the same module in reference report
        ref_libs = []
        if module_name in reference_report.modules:
            ref_module = reference_report.modules[module_name]
            if lib_section_marker in ref_module:
                ref_parts = ref_module.split(lib_section_marker, 1)
                if len(ref_parts) == 2:
                    ref_remaining = ref_parts[1]
                    ref_lib_parts = ref_remaining.split(lib_section_end, 1)
                    if len(ref_lib_parts) >= 1:
                        ref_lib_section = ref_lib_parts[0]
                        
                        for match in lib_pattern.finditer(ref_lib_section):
                            lib_path = match.group(1)
                            lib_info = match.group(2)
                            lib_name = self._extract_library_name(lib_info)
                            
                            normalized_path = lib_path.replace('\\', '/').lower()
                            
                            ref_libs.append({
                                'path': lib_path,
                                'normalized_path': normalized_path,
                                'name': lib_name,
                                'info': lib_info
                            })
        
        if not ref_libs:
            return module_content
        
        # Reorder libraries based on reference
        reordered_libs = []
        used_indices = set()
        
        # Match by exact path and add in reference order
        for ref_lib in ref_libs:
            for i, curr_lib in enumerate(current_libs):
                if i not in used_indices and ref_lib['normalized_path'] == curr_lib['normalized_path']:
                    reordered_libs.append(curr_lib)
                    used_indices.add(i)
                    break
        
        # Add remaining libraries (not in reference) in their original order
        for i, lib in enumerate(current_libs):
            if i not in used_indices:
                reordered_libs.append(lib)
        
        # Rebuild lib section with reordered libraries
        new_lib_section = '\n'.join(lib['full'] for lib in reordered_libs)
        if new_lib_section:
            new_lib_section = '\n' + new_lib_section + '\n'
        
        return before_lib_section + lib_section_marker + new_lib_section + lib_section_end + after_lib_section
    
    def _extract_library_name(self, lib_info):
        """Extract library name from {LibName: ...} format."""
        match = re.search(r'\{([^:]+):', lib_info)
        if match:
            return match.group(1).strip()
        return None


def verify_report_integrity(original_report, output_file_path, description):
    """Verify that the output file has the same structure as the original."""
    print(f"\nVerifying {description}...")
    
    # Load the output file
    output_report = BuildReport(output_file_path)
    
    # Check module count
    original_module_count = len(original_report.module_order)
    output_module_count = len(output_report.module_order)
    
    print(f"  Module count: {output_module_count} (expected: {original_module_count})", end="")
    if original_module_count == output_module_count:
        print(" OK")
    else:
        print(f" MISMATCH!")
        return False
    
    # Check library count for each module
    mismatches = []
    for module_name in original_report.module_order:
        original_lib_count = original_report.get_library_count(module_name)
        output_lib_count = output_report.get_library_count(module_name)
        
        if original_lib_count != output_lib_count:
            mismatches.append({
                'module': module_name,
                'original': original_lib_count,
                'output': output_lib_count
            })
    
    if mismatches:
        print(f"  Library count mismatches: {len(mismatches)} modules FAILED")
        print(f"\n  First 10 mismatches:")
        for mismatch in mismatches[:10]:
            module = mismatch['module']
            orig = mismatch['original']
            out = mismatch['output']
            print(f"    - {module}: {out} (expected: {orig})")
        return False
    else:
        print(f"  Library counts: All {original_module_count} modules verified OK")
        return True


def main():
    """Main function."""
    if len(sys.argv) != 3:
        print("Usage: python reorder_buildreport.py <report1> <report2>")
        print("\nArguments:")
        print("  report1  - First build report (reference for module order)")
        print("  report2  - Second build report (will be reordered)")
        print("\nOutput:")
        print("  BuildReport-reorder_driver.txt (modules reordered only)")
        print("  BuildReport-reorder_driver_and_lib.txt (modules and libraries reordered)")
        sys.exit(1)
    
    report1_path = sys.argv[1]
    report2_path = sys.argv[2]
    
    # Validate input files
    if not Path(report1_path).exists():
        print(f"Error: File not found: {report1_path}")
        sys.exit(1)
    
    if not Path(report2_path).exists():
        print(f"Error: File not found: {report2_path}")
        sys.exit(1)
    
    # Parse both reports
    print(f"\nParsing {report1_path}...")
    report1 = BuildReport(report1_path)
    
    print(f"Parsing {report2_path}...")
    report2 = BuildReport(report2_path)
    
    # Reorder report2 based on report1's module order
    print(f"\nReordering modules based on {report1_path}...")
    new_order = report2.reorder_modules(report1.module_order)
    
    # Show statistics
    common_modules = set(report1.module_order) & set(report2.module_order)
    only_in_report1 = set(report1.module_order) - set(report2.module_order)
    only_in_report2 = set(report2.module_order) - set(report1.module_order)
    
    print(f"\nStatistics:")
    print(f"  Common modules: {len(common_modules)}")
    print(f"  Only in report1: {len(only_in_report1)}")
    print(f"  Only in report2: {len(only_in_report2)}")
    
    if only_in_report1:
        print(f"\n  Modules only in {report1.filepath.name} (first 10):")
        for module in list(only_in_report1)[:10]:
            print(f"    - {module}")
    
    if only_in_report2:
        print(f"\n  Modules only in {report2.filepath.name} (first 10):")
        for module in list(only_in_report2)[:10]:
            print(f"    - {module}")
    
    # Save reordered report (driver only)
    print(f"\nSaving reordered report (driver only)...")
    report2.save("BuildReport-reorder_driver.txt")
    
    # Save reordered report (driver and library)
    print(f"Saving reordered report (driver and library)...")
    report2.save("BuildReport-reorder_driver_and_lib.txt", reorder_libraries=True, reference_report=report1)
    
    # Verify integrity
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    driver_only_ok = verify_report_integrity(
        report2,
        "BuildReport-reorder_driver.txt",
        "BuildReport-reorder_driver.txt"
    )
    
    driver_and_lib_ok = verify_report_integrity(
        report2,
        "BuildReport-reorder_driver_and_lib.txt",
        "BuildReport-reorder_driver_and_lib.txt"
    )
    
    print("\n" + "="*80)
    if driver_only_ok and driver_and_lib_ok:
        print("✓ All verifications passed!")
    else:
        print("✗ Verification failed! Please check the output files.")
    print("="*80)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
