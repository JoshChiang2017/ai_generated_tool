#!/usr/bin/env python3
"""
Memory Map Visualizer - Visualize memory layout with multiple regions
Generated with AI assistance (GitHub Copilot + ChatGPT ~75%)

Dependencies:
pip install matplotlib
"""

import os
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import textwrap
from datetime import datetime

# Raw regions data 
raw_regions = [
    # rdv3_fw_config.dts
    ("FW_CONFIG",      "tb_fw-config",   0x0001f300, 0x00000200),
    ("FW_CONFIG",      "tos_fw-config",  0x0001f500, 0x00001000),
    ("FW_CONFIG",      "nt_fw-config",   0xF3000000, 0x00100000),
    # atf_boot info
    ("atf_boot",       "FW_CONFIG_ID",   0x0001a010, 0x000001bb),
    ("atf_boot",       "BL2",            0x00090000, 0x000196da),
    ("atf_boot",       "BL31",           0x0006b000, 0x00018262),
    ("atf_boot",       "BL32",           0xfa889000, 0x00038620),
    # rdv3_spmc_sp_manifest.dts
    ("TOS_FW_CONFIG",  "memory-sp",      0xfa889000, 0x00400000),
    ("TOS_FW_CONFIG",  "memory-heap",    0xfad00000, 0x00500000),
    ("TOS_FW_CONFIG",  "ns-memory-sp",   0x80000000, 0x78FE0000),
    ("TOS_FW_CONFIG",  "ns-memory-cper", 0xFA879000, 0x00010000),
    ("TOS_FW_CONFIG",  "device-memory",  0x04000000, 0x04000000),
    ("TOS_FW_CONFIG",  "vm1",            0xFAA00000, 0x00300000),
    # hafnium boot log
    ("hafnium",        "data",           0xfa8c1000, 0x000FD000),
    ("hafnium",        "stacks",         0xfa9c9000, 0x00020000),
    ("hafnium",        "text",           0xfa889000, 0x0002B000),
    ("hafnium",        "rodata",         0xfa8b4000, 0x0000D000),
    # rdv3_stmm_config.dts
    ("stmm_config",    "heap",           0xfad00000, 0x00500000),
    ("stmm_config",    "shared-buff",    0xfae89000, 0x00010000),
    ("stmm_config",    "ns-comm",        0xf3200000, 0x00030000),
    ("stmm_config",    "cper-buffer",    0xFA879000, 0x00010000),
]

class Region:
    def __init__(self, group, name, addr, size):
        self.name = name
        self.addr = addr
        self.size = size
        self.end = addr + size
        self.group = group
        self.log2size = self._log2(size) if size > 0 else 0
        self.track = 0

    def _log2(self, n):
        # Bitwise calculation of log2
        r = 0
        while n > 1:
            n >>= 1
            r += 1
        return r

class MemoryMapManager:
    ALIGN_WIDTH = 15
    
    def __init__(self, raw_regions):        
        self.regions = [Region(group, name, addr, size) for group, name, addr, size in raw_regions]
        self.groups = list(dict.fromkeys(r.group for r in self.regions))
        
        self._calculate_y_coordinates()
        self._calculate_tracks()
        self._calculate_group_base_x()
    
    def _calculate_y_coordinates(self):
        """Calculate Y-axis coordinate compression"""
        key_addresses = set()
        for r in self.regions:
            key_addresses.add(r.addr)
            key_addresses.add(r.end)
        self.sorted_key_addresses = sorted(list(key_addresses))
        self.addr_to_compressed_y = {addr: i for i, addr in enumerate(self.sorted_key_addresses)}
    
    def _calculate_tracks(self):
        """Calculate track position for each region to avoid overlap"""
        for group_name in self.groups:
            group_regs = self.get_regions_by_group(group_name)
            tracks = []
            
            for reg in group_regs:
                # Find non-overlapping track starting from track 0
                placed = False
                for t, track_end_list in enumerate(tracks):
                    # Check if it overlaps with all regions in this track
                    overlap = any(not (reg.end <= r.addr or reg.addr >= r.end) for r in track_end_list)
                    if not overlap:
                        reg.track = t
                        track_end_list.append(reg)
                        placed = True
                        break
                if not placed:
                    reg.track = len(tracks)
                    tracks.append([reg])
    
    def _calculate_group_base_x(self):
        """Calculate base X position for each group, considering track count"""
        self.group_base_x = {}
        current_x = 0
        
        for group_name in self.groups:
            self.group_base_x[group_name] = current_x
            group_regs = self.get_regions_by_group(group_name)
            max_track = max(r.track for r in group_regs) if group_regs else 0
            current_x += max_track + 1
    
    def get_group_x_pos(self, group_name, track):
        return self.group_base_x[group_name] + track
    
    def get_group_separator_positions(self):
        return [(self.group_base_x[self.groups[i]] - 0.5) for i in range(1, len(self.groups))]
    
    def get_x_limits(self):
        min_x = min(self.group_base_x.values())
        max_x = max(self.group_base_x.values()) + max(r.track for r in self.regions)
        return min_x - 0.5, max_x + 0.5

    def debug_print(self):
        print("=== Memory Map Manager Debug Info ===")
        print(f"{'groups':<{self.ALIGN_WIDTH}}: {self.groups}")
        print(f"{'group_base_x':<{self.ALIGN_WIDTH}}: {self.group_base_x}")
        print(f"{'Total regions':<{self.ALIGN_WIDTH}}: {len(self.regions)}")
        for group_name in self.groups:
            group_regions = self.get_regions_by_group(group_name)
            print(f"  {group_name:<{self.ALIGN_WIDTH}}: {len(group_regions)} regions")
        
        print("\n=== Individual Regions ===")
        print(f"  {'Group':<{self.ALIGN_WIDTH}}"
              f" {'Name':<{self.ALIGN_WIDTH}}"
              f" {'Start':>{self.ALIGN_WIDTH}}"
              f" {'End':>{self.ALIGN_WIDTH}}"
              f" {'Size':>{self.ALIGN_WIDTH}}"
              f" {'Track':>{self.ALIGN_WIDTH}}")
        print("-" * 100)
        for r in self.regions:
            addr_str = f"{r.addr:#x}"
            end_str = f"{r.end:#x}"
            size_str = f"{r.size:#x}"
            print(f"  {r.group:<{self.ALIGN_WIDTH}}"
                  f" {r.name:<{self.ALIGN_WIDTH}}"
                  f" {addr_str:>{self.ALIGN_WIDTH}}"
                  f" {end_str:>{self.ALIGN_WIDTH}}"
                  f" {size_str:>{self.ALIGN_WIDTH}}"
                  f" {r.track:>{self.ALIGN_WIDTH}}")

    def get_regions_by_group(self, group_name):
        """Return all regions matching group_name"""
        return [r for r in self.regions if r.group == group_name]


def main():
    manager = MemoryMapManager(raw_regions)
    #manager.debug_print()

    # 2. Draw plot
    fig_width = 6 + len(manager.groups) * 2
    fig, ax = plt.subplots(figsize=(fig_width, 10))

    # 3. Draw bars by group
    for group_name in manager.groups:
        group_regs = manager.get_regions_by_group(group_name)

        for reg in group_regs:
            x_pos = manager.get_group_x_pos(group_name, reg.track)
            y_start = manager.addr_to_compressed_y[reg.addr]
            y_height = manager.addr_to_compressed_y[reg.end] - manager.addr_to_compressed_y[reg.addr]

            ax.bar(x=x_pos, height=y_height, bottom=y_start, width=0.9, alpha=0.6,
                label=f"(0x{reg.addr:08X}~0x{reg.end:08X}) <{reg.group}> {reg.name}")

            ax.text(x_pos, y_start + y_height / 2, textwrap.fill(reg.name, width=10),
                    ha='center', va='center', color='black',
                    fontsize=10) # fontweight='bold'

    # Group separator lines
    for xpos in manager.get_group_separator_positions():
        ax.axvline(x=xpos, color='blue', linestyle='--', linewidth=1, alpha=0.5)

    # --- Draw horizontal grid lines ---
    x_limit_start, x_limit_end = manager.get_x_limits()

    for y_coord in manager.addr_to_compressed_y.values():
        ax.hlines(y_coord, xmin=x_limit_start, xmax=x_limit_end,
                color='gray', linestyle='--', linewidth=0.5, alpha=0.6)

    # --- Y-axis (address) setup ---
    def format_addr(compressed_y, pos):
        if 0 <= compressed_y < len(manager.sorted_key_addresses):
            return hex(manager.sorted_key_addresses[int(compressed_y)])
        return ''

    ax.set_yticks(list(manager.addr_to_compressed_y.values()))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_addr))

    # --- X-axis (track) setup ---
    ax.set_xticks([manager.group_base_x[g] for g in manager.groups])
    ax.set_xticklabels(manager.groups)

    # --- Boundaries and title ---
    ax.set_xlim(x_limit_start, x_limit_end)
    ax.set_ylim(-0.5, len(manager.sorted_key_addresses) - 0.5)

    ax.set_title("Memory Map", fontsize=14)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', title="Regions (Address & Size)")

    plt.tight_layout()
    
    # Save to current directory with timestamped
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"memory_map_{timestamp}.png"
    plt.savefig(output_file, dpi=150)
    print(f"Memory map saved to: {os.path.abspath(output_file)}")
    
    plt.show()

if __name__ == "__main__":
    main()