// SPDX-License-Identifier: GPL-2.0-only
/* Pulse Probe P1.0.0: optional, read-only Linux kernel module.
 * No scheduler, VFS, security-policy or driver hooks; safe removal.
 */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/mm.h>
#include <linux/cpu.h>
#include <linux/ktime.h>

#define PULSE_PROBE_VERSION "P1.0.0"
static struct proc_dir_entry *pulse_root;

static int pulse_status_show(struct seq_file *m, void *v)
{
    struct sysinfo mem;
    si_meminfo(&mem);
    seq_printf(m, "pulse_probe=%s\n", PULSE_PROBE_VERSION);
    seq_puts(m, "scope=read-only diagnostics; no scheduler or security hooks\n");
    seq_printf(m, "online_cpus=%u\n", num_online_cpus());
    seq_printf(m, "boottime_seconds=%llu\n",
               (unsigned long long)ktime_get_boottime_seconds());
    seq_printf(m, "ram_pages=%lu\n", mem.totalram);
    seq_printf(m, "free_pages=%lu\n", mem.freeram);
    return 0;
}

static int __init pulse_probe_init(void)
{
    pulse_root = proc_mkdir("pulse", NULL);
    if (!pulse_root)
        return -ENOMEM;
    if (!proc_create_single("status", 0444, pulse_root, pulse_status_show)) {
        proc_remove(pulse_root);
        pulse_root = NULL;
        return -ENOMEM;
    }
    pr_info("Pulse Probe %s loaded (read-only)\n", PULSE_PROBE_VERSION);
    return 0;
}

static void __exit pulse_probe_exit(void)
{
    proc_remove(pulse_root);
    pr_info("Pulse Probe unloaded\n");
}

module_init(pulse_probe_init);
module_exit(pulse_probe_exit);
MODULE_AUTHOR("Pulse open kernel project");
MODULE_DESCRIPTION("Pulse read-only kernel diagnostic prototype");
MODULE_LICENSE("GPL");
MODULE_VERSION("1.0.0");
