# 本程序是基于epbf+bcc开发的，对内核中断关闭状态时长进行监测的探针
# 参考了bcc提供的工具中的criticalstat.py

# 运行前请确保
# 1、根据[bcc官方仓库安装说明]中的说明，以源码方式安装了最新版的bcc以及相关库并成功运行实例程序
# 2、linux内核版本>5.xxxx以支持新版ebpf特性
# 3、在PREEMPTIRQ.....配置下构建linux内核（xx和XX可以任选一个或选两个）

# 使用方法: [sudo] [python3] probe.py [-h] [-p] [-i] [-d DURATION]

# By c0dend

from __future__ import print_function
from bcc import BPF
import argparse
import sys
import subprocess
import os.path

examples=""

parser = argparse.ArgumentParser(
    description="probe irq/preempt off state",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=examples)

parser.add_argument("-p", "--preemptoff", action="store_true",
                    help="Probe preemption off")

parser.add_argument("-i", "--irqoff", action="store_true",
                    help="Probe irq off")

parser.add_argument("-d", "--duration", default=100,
                    help="Filter duration below this(us)")

args = parser.parse_args()

preemptoff = False
irqoff = False

if args.irqoff:
    irqoff = True
if args.preemptoff:
    preemptoff = True

if (not args.irqoff) and (not args.preemptoff):
    irqoff = True
    #preemptoff = True

# open subprocess to output kernal debugfs path
debugfs_path = subprocess.Popen ("cat /proc/mounts | grep -w debugfs" +
    " | awk '{print $2}'",
    shell=True,
    stdout=subprocess.PIPE).stdout.read().split(b"\n")[0]

#unable to find document
if debugfs_path == "":
    print("ERROR: Unable to find debugfs mount point");
    sys.exit(0)

trace_path = debugfs_path + b"/tracing/events/preemptirq/";

#unable to find tracepoint
if irqoff:
    if (not os.path.exists(trace_path + b"irq_disable") or
        not os.path.exists(trace_path + b"irq_enable")):
        print("ERROR: required tracing point are not available\n" +
        "Make sure the kernel is built with CONFIG_DEBUG_PREEMPT " +
        "CONFIG_PREEMPT_TRACER " +
        "CONFIG_PREEMPTIRQ_TRACEPOINTS"+
        "(CONFIG_PREEMPTIRQ_EVENTS older than kernel 4.19) and CONFIG_TRACE_IRQFLAGS enabled.\n"
        "Also please disable " +
        "CONFIG_PROVE_LOCKING and CONFIG_LOCKDEP on older kernels.")
        
        
if preemptoff:
    if (not os.path.exists(trace_path + b"preempt_disable") or
        not os.path.exists(trace_path + b"preempt_enable")):
        print("ERROR: required tracing point are not available\n" +
        "Make sure the kernel is built with CONFIG_DEBUG_PREEMPT " +
        "CONFIG_PREEMPT_TRACER " +
        "CONFIG_PREEMPTIRQ_TRACEPOINTS"+
        "(CONFIG_PREEMPTIRQ_EVENTS older than kernel 4.19) and TRACE_PREEMPT_TOGGLE enabled.\n"
        "Also please disable " +
        "CONFIG_PROVE_LOCKING and CONFIG_LOCKDEP on older kernels.")


#C program
same_bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

enum addr_offs {
    START_CALLER_OFF,
    START_PARENT_OFF,
    END_CALLER_OFF,
    END_PARENT_OFF
};

//data struct in sts to record in_disable stat and if in_idle
struct start_data {
    u32 addr_offs[2];
    u64 ts;
    int idle_skip;//skip: in idle
    int active;//active: in disable
};

//output data
struct data_t {
    u64 time;
    s64 stack_id;
    u32 cpu;
    u64 id;
    u32 addrs[4];   /* indexed by addr_offs */
    char comm[TASK_COMM_LEN];
};

BPF_STACK_TRACE(stack_traces, 16384);
BPF_PERCPU_ARRAY(sts, struct start_data, 1);
BPF_PERCPU_ARRAY(isidle, u64, 1);
BPF_PERF_OUTPUT(events);

/*
 * In the below code we install tracepoint probes on preempt or
 * IRQ disable/enable critical sections and idle events, the cases
 * are combinations of 4 different states.
 * The states are defined as:
 * CSenter: A critical section has been entered. Either due to
 *          preempt disable or irq disable.
 * CSexit: A critical section has been exited. Either due to
 *         preempt enable or irq enable.
 * Ienter: The CPU has entered an idle state.
 * Iexit: The CPU has exited an idle state.
 *
 * The scenario we are trying to detect is if there is an overlap
 * between Critical sections and idle entry/exit. If there are any
 * such cases, we avoid recording those critical sections since they
 * are not worth while to record and just add noise.
 */
TRACEPOINT_PROBE(power, cpu_idle)
{
    int idx = 0;
    u64 val;
    struct start_data *stdp, std;

    // Mark active sections as that they should be skipped

    // Handle the case CSenter, Ienter, CSexit, Iexit
    // Handle the case CSenter, Ienter, Iexit, CSexit
    stdp = sts.lookup(&idx);
    if (stdp && stdp->active) {
        /*
         * Due to verifier issues, we have to copy contents
         * of stdp onto the stack before the update.
         * Fix it to directly update once kernel patch d71962f
         * becomes more widespread.
         */
        std = *stdp;
        std.idle_skip = 1;
        sts.update(&idx, &std);
    }

    // Mark CPU as actively within idle or not.
    if (args->state < 100) {
        //set is idle
        val = 1;
        isidle.update(&idx, &val);
    } else {
        val = 0;
        isidle.update(&idx, &val);
    }
    return 0;
}

static int in_idle(void)
{
     u64 *idlep;
     int idx = 0;

    // Skip event if we're in idle loop
    idlep = isidle.lookup(&idx);
    if (idlep && *idlep)
        return 1;
    return 0;
}

//reset start_data to sts
static void reset_state(void)
{
    int idx = 0;
    struct start_data s = {};

    sts.update(&idx, &s);
}

"""
change_bpf_text = """

TRACEPOINT_PROBE(preemptirq, TYPE_disable)
{
    int idx = 0;
    struct start_data s;

    // Handle the case Ienter, CSenter, CSexit, Iexit
    // Handle the case Ienter, CSenter, Iexit, CSexit
    if (in_idle()) {
        //in idle, skip this trace, reset sts state
        reset_state();
        return 0;
    }

    //record in_disable stat
    u64 ts = bpf_ktime_get_ns();

    s.idle_skip = 0;
    s.addr_offs[START_CALLER_OFF] = args->caller_offs;
    s.addr_offs[START_PARENT_OFF] = args->parent_offs;
    s.ts = ts;
    s.active = 1;

    sts.update(&idx, &s);
    return 0;
}

TRACEPOINT_PROBE(preemptirq, TYPE_enable)
{
    int idx = 0;
    u64 start_ts, end_ts, diff;
    struct start_data *stdp;

    // Handle the case CSenter, Ienter, CSexit, Iexit
    // Handle the case Ienter, CSenter, CSexit, Iexit
    if (in_idle()) {
        reset_state();
        return 0;
    }

    stdp = sts.lookup(&idx);
    if (!stdp) {
        reset_state();
        return 0;
    }

    // Handle the case Ienter, Csenter, Iexit, Csexit
    if (!stdp->active) {
        reset_state();
        return 0;
    }

    // Handle the case CSenter, Ienter, Iexit, CSexit
    if (stdp->idle_skip) {
        reset_state();
        return 0;
    }

    end_ts = bpf_ktime_get_ns();
    start_ts = stdp->ts;

    if (start_ts > end_ts) {
        reset_state();
        return 0;
    }

    diff = end_ts - start_ts;

    if (diff < DURATION) {
        reset_state();
        return 0;
    }

    u64 id = bpf_get_current_pid_tgid();
    struct data_t data = {};

    if (bpf_get_current_comm(&data.comm, sizeof(data.comm)) == 0) {
        data.addrs[START_CALLER_OFF] = stdp->addr_offs[START_CALLER_OFF];
        data.addrs[START_PARENT_OFF] = stdp->addr_offs[START_PARENT_OFF];
        data.addrs[END_CALLER_OFF] = args->caller_offs;
        data.addrs[END_PARENT_OFF] = args->parent_offs;

        data.id = id;
        data.stack_id = stack_traces.get_stackid(args, 0);
        data.time = diff;
        data.cpu = bpf_get_smp_processor_id();
        events.perf_submit(args, &data, sizeof(data));
    }

    reset_state();
    return 0;
}
"""


bpf_text=same_bpf_text
change_bpf_text = change_bpf_text.replace('DURATION', '{}'.format(int(args.duration) * 1000))

#maybe not use preemptoff
if preemptoff:
    bpf_text = bpf_text+change_bpf_text.replace('TYPE', 'preempt')
if irqoff:
    bpf_text = bpf_text+change_bpf_text.replace('TYPE', 'irq')

    

b = BPF(text=bpf_text)

def get_syms(kstack):
    syms = []

    for addr in kstack:
        s = b.ksym(addr, show_offset=True)
        syms.append(s)

    return syms


# process event
def print_event(cpu, data, size):
    try:
        global b
        event = b["events"].event(data)
        stack_traces = b['stack_traces']
        #text section addr
        stext = b.ksymname('_stext')

        print("===================================")
        print("TASK: %s (pid %5d tid %5d) Total Time: %-9.3fus\n\n" % (event.comm, \
            (event.id >> 32), (event.id & 0xffffffff), float(event.time) / 1000), end="")
        print("Section start: {} -> {}".format(b.ksym(stext + event.addrs[0]), b.ksym(stext + event.addrs[1])))
        print("Section end:   {} -> {}".format(b.ksym(stext + event.addrs[2]), b.ksym(stext + event.addrs[3])))

        if event.stack_id >= 0:
            kstack = stack_traces.walk(event.stack_id)
            syms = get_syms(kstack)
            if not syms:
                return

            for s in syms:
                print("  ", end="")
                print("%s" % s)
        else:
            print("NO STACK FOUND DUE TO COLLISION")
        print("===================================")
        print("")
    except Exception:
        sys.exit(0)

b["events"].open_perf_buffer(print_event, page_cnt=256)

print("Finding critical section with {} disabled for > {}us".format( \
    ('preempt and IRQ' if (preemptoff and irqoff) else ('preempt' if preemptoff else 'IRQ' )), \
    args.duration))

while 1:
    try:
        b.perf_buffer_poll()
    except KeyboardInterrupt:
        exit()
