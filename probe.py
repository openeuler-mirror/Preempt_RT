# 本程序是基于eBPF+BCC开发的，对内核中断关闭状态时长进行监测的探针

# 运行前请确保:
# 1、根据 https://github.com/iovisor/bcc/blob/master/INSTALL.md 中的说明，以源码方式安装了最新版的BCC以及相关库并成功运行实例程序
# 2、linux内核版本大于5.8,以支持新版eBPF特性
# 3、在CONFIG_PREEMPTIRQ_TRACEPOINTS、CONGIF_DEBUG_PREEMPT、CONFIG_PREEMPT_TRACER配置选项及其依赖下构建linux内核

# 使用方法: [sudo] [python3] probe.py [-h] [-p] [-i] [-d DURATION]

# 2022 杨盾 c0dend


from bcc import BPF
import argparse
import sys
import subprocess
import os.path
import time
import ctypes as ct
import psutil

#---------------------------args------------------------#
examples=""

parser = argparse.ArgumentParser(
    description="probe irq/preempt off state, related resources and find longest irq/preempt off group",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=examples)

parser.add_argument("-p", "--preemptoff", action="store_true",
                    help="Probe preemption off")

parser.add_argument("-i", "--irqoff", action="store_true",
                    help="Probe irq off")

parser.add_argument("-d", "--duration", default=500,
                    help="Filter duration below this(us)")


args = parser.parse_args()

preemptoff = False
irqoff = False

if args.irqoff:
    irqoff = True
if args.preemptoff:
    preemptoff = True

# default probe irpoff
if (not args.irqoff) and (not args.preemptoff):
    irqoff = True

# open subprocess to output kernal debugfs path
debugfs_path = subprocess.Popen ("cat /proc/mounts | grep -w debugfs" +
    " | awk '{print $2}'",
    shell=True,
    stdout=subprocess.PIPE).stdout.read().split(b"\n")[0]

# unable to find document
if debugfs_path == "":
    print("ERROR: Unable to find debugfs mount point");
    sys.exit(0)

trace_path = debugfs_path + b"/tracing/events/preemptirq/";

# unable to find tracepoint
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


#--------------------------header file and data structure-------------------------#
bpf_text="""
#include<linux/spinlock_types.h>
#include<linux/spinlock.h>
#include<linux/fs.h>
#include<uapi/linux/ptrace.h>
#include<linux/sched.h>
#include<linux/fdtable.h>
#include<linux/net.h>

//if enabled storage
BPF_ARRAY(enabled,   u64, 1);
//record total eBPF time
BPF_ARRAY(tot_time,   u64, 1);

//storage lock data
struct lock_data_t {
    u64 id;
    void *lock;
};
BPF_HASH(lock_hash,struct lock_data_t, u64,102400);

//storage file data
struct file_data_t {
    u64 id;
    u64 inode;
};
BPF_HASH(file_hash,struct file_data_t, u64,102400);

//storage socket data
struct sock_data_t {
    u64 id;
    void *sock;
};
BPF_HASH(sock_hash,struct sock_data_t, u64,102400);

//stack trace address
enum addr_offs {
    START_CALLER_OFF,
    START_PARENT_OFF,
    END_CALLER_OFF,
    END_PARENT_OFF
};

//data structure to record in_disable stat and if in_idle
struct start_data {
    u32 addr_offs[2];
    u64 ts;
    int idle_skip;//skip: in idle
    int active;//active: in disable
};

//CS output data, CS(critical section, refer to criticalstat.py from BCC/tools)
struct cs_data_t {
    u64 ts;            //time start
    u64 time;          //time diff
    s64 stack_id;
    u32 cpu;
    u64 id;
    u32 addrs[4];      //indexed by addr_offs 
    char comm[TASK_COMM_LEN];

};

//used to output CS info
BPF_STACK_TRACE(stack_traces, 16384);
BPF_PERCPU_ARRAY(sts, struct start_data, 1);
BPF_PERCPU_ARRAY(isidle, u64, 1);
BPF_RINGBUF_OUTPUT(cs_events,256);


"""
#--------------------------CS C program-------------------------#
fixed_cs_prog = """

//record current time to total time
static void AddToTalTime(u64 st_time)
{
    int key = 0;
    u64 *ret;
    ret = tot_time.lookup(&key);//old time
    if(ret)
    {
        u64 new_time=*ret+bpf_ktime_get_ns()-st_time;
        tot_time.update(&key,&new_time);
    }

}

//trace idle state to avoid recording critical sections overlapping with idle
//refer to criticalstat.py
TRACEPOINT_PROBE(power, cpu_idle)
{
    u64 st_time=bpf_ktime_get_ns();
    int idx = 0;
    u64 val;
    struct start_data *stdp, std;

    // Mark active sections as that they should be skipped

    // Handle the case CSenter, Ienter, CSexit, Iexit
    // Handle the case CSenter, Ienter, Iexit, CSexit
    stdp = sts.lookup(&idx);
    if (stdp && stdp->active) {
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
    AddToTalTime(st_time);
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

//reset start_data
static void reset_state(void)
{
    int idx = 0;
    struct start_data s = {};

    sts.update(&idx, &s);
}

"""
changed_cs_prog = """

//some of the content will changed depending on tracepoints we need

//disable will record start info
TRACEPOINT_PROBE(preemptirq, TYPE_disable)
{
    u64 st_time=bpf_ktime_get_ns();
    int idx = 0;
    struct start_data s;

    // Handle the case Ienter, CSenter, CSexit, Iexit
    // Handle the case Ienter, CSenter, Iexit, CSexit
    if (in_idle()) {
        //in idle, skip this trace, reset state
        reset_state();
        AddToTalTime(st_time);
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
    AddToTalTime(st_time);
    return 0;
}

//enable will output recorded info
TRACEPOINT_PROBE(preemptirq, TYPE_enable)
{
    u64 st_time=bpf_ktime_get_ns();
    int idx = 0;
    u64 start_ts, end_ts, diff;
    struct start_data *stdp;

    // Handle the case CSenter, Ienter, CSexit, Iexit
    // Handle the case Ienter, CSenter, CSexit, Iexit
    if (in_idle()) {
        reset_state();
        AddToTalTime(st_time);
        return 0;
    }

    stdp = sts.lookup(&idx);
    if (!stdp) {
        reset_state();
        AddToTalTime(st_time);
        return 0;
    }

    // Handle the case Ienter, Csenter, Iexit, Csexit
    if (!stdp->active) {
        reset_state();
        AddToTalTime(st_time);
        return 0;
    }

    // Handle the case CSenter, Ienter, Iexit, CSexit
    if (stdp->idle_skip) {
        reset_state();
        AddToTalTime(st_time);
        return 0;
    }

    end_ts = bpf_ktime_get_ns();
    start_ts = stdp->ts;

    if (start_ts > end_ts) {
        reset_state();
        AddToTalTime(st_time);
        return 0;
    }

    diff = end_ts - start_ts;

    if (diff < DURATION) {
        reset_state();
        AddToTalTime(st_time);
        return 0;
    }

    u64 id = bpf_get_current_pid_tgid();
    struct cs_data_t cs_data = {};

    //get info
    if (bpf_get_current_comm(&cs_data.comm, sizeof(cs_data.comm)) == 0) {
        cs_data.addrs[START_CALLER_OFF] = stdp->addr_offs[START_CALLER_OFF];
        cs_data.addrs[START_PARENT_OFF] = stdp->addr_offs[START_PARENT_OFF];
        cs_data.addrs[END_CALLER_OFF] = args->caller_offs;
        cs_data.addrs[END_PARENT_OFF] = args->parent_offs;
        
        cs_data.ts= start_ts;
        cs_data.id = id;
        cs_data.stack_id = stack_traces.get_stackid(args, 0);
        cs_data.time = diff;
        cs_data.cpu = bpf_get_smp_processor_id();
        cs_events.ringbuf_output(&cs_data, sizeof(cs_data),0);
    }

    reset_state();
    AddToTalTime(st_time);
    return 0;
}
"""

bpf_text=bpf_text+fixed_cs_prog
changed_cs_prog = changed_cs_prog.replace('DURATION', '{}'.format(int(args.duration) * 1000))

#maybe not use preemptoff
if preemptoff:
    bpf_text = bpf_text+changed_cs_prog.replace('TYPE', 'preempt')
if irqoff:
    bpf_text = bpf_text+changed_cs_prog.replace('TYPE', 'irq')


#--------------------------spin_unlock C program-------------------------#
lock_prog="""

static bool is_enabled(void)
{
    int key = 0;
    u64 *ret;

    ret = enabled.lookup(&key);
    return ret && *ret == 1;
}


int unlock_enter(struct pt_regs *ctx,struct spinlock_t *lock)
{

    if (!is_enabled())
        return 0;
    u64 st_time=bpf_ktime_get_ns();
    
    u64 id = bpf_get_current_pid_tgid();

    u64 cur_time = bpf_ktime_get_ns();
    
    struct lock_data_t cur_lock={id,(void*)lock};
    
    lock_hash.update(&cur_lock, &cur_time);
    AddToTalTime(st_time);
    return 0;
}
"""




bpf_text=bpf_text+lock_prog


#--------------------------vfs C program-------------------------#
file_prog="""


int vfs_read_write_enter(struct pt_regs *ctx,struct file *file)
{

    if (!is_enabled())
        return 0;
    u64 st_time=bpf_ktime_get_ns();
    
    u64 id = bpf_get_current_pid_tgid();

    u64 cur_time = bpf_ktime_get_ns();
    
    struct file_data_t cur_file={id,file->f_inode->i_ino};
    
    file_hash.update(&cur_file, &cur_time);
    AddToTalTime(st_time);
    return 0;
}
"""


bpf_text=bpf_text+file_prog

    
#--------------------------sock C program-------------------------#
sock_prog="""


int sock_recv_send_msg_enter(struct pt_regs *ctx,struct socket *sock,struct msghdr *msg)
{

    if (!is_enabled())
        return 0;
    u64 st_time=bpf_ktime_get_ns();
    
    u64 id = bpf_get_current_pid_tgid();

    u64 cur_time = bpf_ktime_get_ns();
    
    struct sock_data_t cur_sock={id,sock};
    
    sock_hash.update(&cur_sock, &cur_time);
    AddToTalTime(st_time);
    return 0;
}
"""


bpf_text=bpf_text+sock_prog

    
#-------------------func--------------------#
# trace stack
def get_syms(kstack):
    syms = []

    for addr in kstack:
        s = b.ksym(addr, show_offset=True)
        syms.append(s)

    return syms

#update resource data
def UpdateLock(locks):
    global hash_map
    for k,v in locks.items():
        if not (k.id in hash_map):
            hash_map[k.id]=[{},{},{}]
        if not (k.lock in hash_map[k.id][0]):
            hash_map[k.id][0][k.lock]=[]
        hash_map[k.id][0][k.lock].append(v.value)

        #print("(pid %5d tid %5d) time: %s lockaddr: %#x\n\n" % \
        #    ((k.id >> 32), (k.id & 0xffffffff), (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(boot_t+float(v.value)/1000000000))) ,k.lock), end="")
    #print("----------------------------------------------------------------------")
        
def UpdateFile(files):
    global hash_map
    for k,v in files.items():
        if not (k.id in hash_map):
            hash_map[k.id]=[{},{},{}]
        if not (k.inode in hash_map[k.id][1]):
            hash_map[k.id][1][k.inode]=[]
        hash_map[k.id][1][k.inode].append(v.value)

        #print("(pid %5d tid %5d) time: %s fileino: %d\n\n" % \
        #    ((k.id >> 32), (k.id & 0xffffffff), (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(boot_t+float(v.value)/1000000000))),k.inode), end="")
    #print("----------------------------------------------------------------------")
        
def UpdateSock(socks):
    global hash_map
    for k,v in socks.items():
        if not (k.id in hash_map):
            hash_map[k.id]=[{},{},{}]
        if not (k.sock in hash_map[k.id][2]):
            hash_map[k.id][2][k.sock]=[]
        hash_map[k.id][2][k.sock].append(v.value)
        #print("(pid %5d tid %5d) time: %s sockaddr: %#x\n\n" % \
        #    ((k.id >> 32), (k.id & 0xffffffff), (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(boot_t+float(v.value)/1000000000))),k.sock), end="")
    #print("----------------------------------------------------------------------")

# union set find func
def Find(pos):
    global p
    if p[pos]!=pos:
        p[pos]=Find(p[pos])
    return p[pos]

# union set merge func
def Merge(a,b):
    global p
    global sz
    pa=Find(a)
    pb=Find(b)
    if pa!=pb:
        p[pa]=pb
        sz[pb]+=sz[pa]

# if got resource time in CS
def InCS(pos,t):
    global start_end_pair
    if t>=start_end_pair[pos][0] and t<=start_end_pair[pos][1]:
        return True
    return False

# if two CS can merge (have edge)
def CanMerge(i,j):
    # have resource in CS and shared with others
    global tid
    global hash_map
    global start_end_pair
    id1=tid[i]
    id2=tid[j]
    
    all_obj1=[]
    all_obj2=[]
    for obj1,v1 in hash_map[id1][0].items():
        for t1 in v1:
            if InCS(i,t1):
                all_obj1.append(obj1)
    
    for obj2,v2 in hash_map[id2][0].items():
        for t2 in v2:
            if InCS(j,t2):
                all_obj2.append(obj2)
            
    for obj1 in all_obj1:
        for obj2 in hash_map[id2][0]:
            if obj1==obj2:
                return True

    for obj1 in hash_map[id1][0]:
        for obj2 in all_obj2:
            if obj1==obj2:
                return True

            
    all_obj1=[]
    all_obj2=[]
    for obj1,v1 in hash_map[id1][1].items():
        for t1 in v1:
            if InCS(i,t1):
                all_obj1.append(obj1)
    
    for obj2,v2 in hash_map[id2][1].items():
        for t2 in v2:
            if InCS(j,t2):
                all_obj2.append(obj2)
            
    for obj1 in all_obj1:
        for obj2 in hash_map[id2][1]:
            if obj1==obj2:
                return True

    for obj1 in hash_map[id1][1]:
        for obj2 in all_obj2:
            if obj1==obj2:
                return True

                       
    all_obj1=[]
    all_obj2=[]
    for obj1,v1 in hash_map[id1][2].items():
        for t1 in v1:
            if InCS(i,t1):
                all_obj1.append(obj1)
    
    for obj2,v2 in hash_map[id2][2].items():
        for t2 in v2:
            if InCS(j,t2):
                all_obj2.append(obj2)
            
    for obj1 in all_obj1:
        for obj2 in hash_map[id2][2]:
            if obj1==obj2:
                return True

    for obj1 in hash_map[id1][2]:
        for obj2 in all_obj2:
            if obj1==obj2:
                return True

    return False

# update the graph
def TryMergeAllCS():
    global union_cnt
    for i in range(0,union_cnt):
        for j in range(i+1,union_cnt):
            pi=Find(i)
            pj=Find(j)
            if(pi!=pj and CanMerge(i,j)):
                Merge(pi,pj)

# have new CS output, update the graph and show the new CS info and max_time CS group info
def RecordCS(ctx, data, size):
    try:
        global b
        global enabled
        global tot_time
        global locks
        global files
        global hash_map
        global union_cnt
        global tid
        global p
        global sz
        global sz_self
        global start_end_pair

        event = b["cs_events"].event(data)

        # update all resources
        enabled[ct.c_int(0)] = ct.c_int(0)
        d_time=tot_time[ct.c_int(0)].value
        tot_time[ct.c_int(0)] = ct.c_int(0)
        UpdateLock(locks)
        locks.clear()
        UpdateFile(files)
        files.clear()
        UpdateSock(socks)
        socks.clear()
        enabled[ct.c_int(0)] = ct.c_int(1)
        
        # data info and eBPF info
        print("\n\n")
        print("Statistical info:")
        print("  Hash map size: %d\n"%(len(hash_map)),end="")
        all_len=0
        for k,v in hash_map.items():
            all_len+=len(v[0])
            all_len+=len(v[1])
            all_len+=len(v[2])
        print("  Hash map items count: %d\n"%(all_len),end="")

        print("  Total eBPF time: %f ms\n"%(float(d_time)/1000000), end="")
        print("======================================================================")

        # output cs info
        print("New CS info:")
        # stack trace
        stack_traces = b['stack_traces']
        #text section addr
        stext = b.ksymname('_stext')

        #print("======================================================================")
        print("  TASK: %s (pid %5d tid %5d) Total CS Time: %-9.3fus\n" % (event.comm, \
            (event.id >> 32), (event.id & 0xffffffff), float(event.time) / 1000), end="")
        print("  Section start: {} -> {}".format(b.ksym(stext + event.addrs[0]), b.ksym(stext + event.addrs[1])))
        print("  Section end:   {} -> {}".format(b.ksym(stext + event.addrs[2]), b.ksym(stext + event.addrs[3])))
        if event.stack_id >= 0:
            print("  STACK TRACE RESULT")
            kstack = stack_traces.walk(event.stack_id)
            syms = get_syms(kstack)
            if not syms:
                return

            for s in syms:
                print("    ", end="")
                print("%s" % s)
        else:
            print("NO STACK FOUND DUE TO COLLISION")
            
        # all resource of new CS
        idx=event.id
        print("  All resources:")
        print("  lockaddr:",end="")
        tcnt=0
        for k in hash_map[idx][0]:
            if(tcnt%8==0):
                print("\n    ",end="")
            print("%#x "%k,end="")
            tcnt+=1
        print("\n",end="")
        print("  fileino:",end="")
        tcnt=0
        for k in hash_map[idx][1]:
            if(tcnt%10==0):
                print("\n    ",end="")
            print("%d "%k,end="")
            tcnt+=1
        print("\n",end="")
        print("  sockaddr:",end="")
        tcnt=0
        for k in hash_map[idx][2]:
            if(tcnt%8==0):
                print("\n    ",end="")
            print("%#x "%k,end="")
            tcnt+=1
        print("\n",end="")
        print("======================================================================")

        # update CS group
        cur_id=event.id
        cur_cs_time=event.time

        tid.append(cur_id)
        p.append(union_cnt)
        sz.append(cur_cs_time)
        sz_self.append(cur_cs_time)
        start_end_pair.append([event.ts,event.ts+cur_cs_time])
        union_cnt=union_cnt+1

        TryMergeAllCS()    

        max_sz=0
        idx=-1

        for i in range(0,union_cnt):
            pi=Find(i)
            if pi==i and sz[i]>max_sz:
                max_sz=sz[i]
                idx=i

        # output max_time CS group info (max connected component and it's nodes and edges)
        print("Longest CS group total time: %-9.3fus\n"%(float(sz[idx]) / 1000),end="")   
        print("All thread in group:")
        pos_in_group=[]
        for i in range(0,union_cnt):
            if p[i]==idx:
                pos_in_group.append(i)
                iid=tid[i]
                print("  pid %5d tid %5d CS Time: %-9.3fus\n" % ((iid >> 32), (iid & 0xffffffff),float(sz_self[i])/1000),end="")
        print("Share common resource:")
        tsz=len(pos_in_group)
        for i in range(0,tsz):
            for j in range(i+1,tsz):
                if CanMerge(pos_in_group[i],pos_in_group[j]):
                    print("  pid %5d tid %5d (%-9.3fus) " % ((tid[pos_in_group[i]] >> 32), (tid[pos_in_group[i]]  & 0xffffffff),float(sz_self[i])/1000),end="")
                    print(" and ",end="")
                    print("  pid %5d tid %5d (%-9.3fus) " % ((tid[pos_in_group[j]]  >> 32), (tid[pos_in_group[j]]  & 0xffffffff),float(sz_self[j])/1000),end="\n")
                    
        print("======================================================================")
    except Exception:
        sys.exit(0)
        
        

#------------------------------main loop--------------------------#

# basic data and structure

# hash_map record resources by id (pid+tid)
hash_map={}
boot_t=psutil.boot_time()
# union_set with sz(CS time)
union_cnt=0
tid=[]
p=[]
sz=[]#cs_size_group
sz_self=[]#cs_size_self
start_end_pair=[]#cs_start_and_end_time

#BPF attach
b = BPF(text=bpf_text)

b.attach_kprobe(event="_raw_spin_unlock", fn_name="unlock_enter")

b.attach_kprobe(event="vfs_read", fn_name="vfs_read_write_enter")
b.attach_kprobe(event="vfs_write", fn_name="vfs_read_write_enter")
#after verify vfs_read/write call __vfs_read/write but cannot attach
#b.attach_kprobe(event="__vfs_read", fn_name="vfs_read_write_enter")
#b.attach_kprobe(event="__vfs_write", fn_name="vfs_read_write_enter")

b.attach_kprobe(event="sock_sendmsg", fn_name="sock_recv_send_msg_enter")
b.attach_kprobe(event="sock_recvmsg", fn_name="sock_recv_send_msg_enter")

#BPF map
b["cs_events"].open_ring_buffer(RecordCS)
enabled = b["enabled"]
tot_time=b["tot_time"]
locks=b["lock_hash"]
files=b["file_hash"]
socks=b["sock_hash"]


ts=0#time start

print("Finding critical section with {} disabled for > {}us".format( \
    ('preempt and IRQ' if (preemptoff and irqoff) else ('preempt' if preemptoff else 'IRQ' )), \
    args.duration))

enabled[ct.c_int(0)] = ct.c_int(1)
while 1:
    try:
        b.ring_buffer_poll()

    except KeyboardInterrupt:
        exit()
