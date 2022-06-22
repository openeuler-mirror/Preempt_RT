# Preempt_RT

openEuler 22.03 LTS 版本新增了 Preempt_RT 内核实时补丁，提供软实时特性。该特性由 Industrial-Control SIG 引入，并得到 Kernel SIG、Embedded SIG 和 Yocto SIG 配合与支持，已经被集成到openEuler 22.03 LTS Server 和 openEuler 22.03 LTS Embedded 中。

## **什么是实时系统**

实时系统的典型定义如下：“所谓实时系统，就是系统中计算结果的正确性不仅取决于计算逻辑的正确性，还取决于产生结果的时间。如果完成时间不符合要求，则可以认为系统发生了问题。”也就是说，不管实时应用程序执行的是何种任务，它不仅需要正确执行该任务而且必须及时完成。当前，Preempt_RT 维护者 Thomas Gleixner 给出的“实时”含义是：它和指定的一样快。

Linux 作为一种通用操作系统，随着时间的推移，在功能和时序行为方面一直在发展，以便适合许多其他更具挑战性的场景；尤其是实时系统对 Linux 的实时性改造一直从未停止过。

对 Linux 进行实时性改造，通常可从两个大的方向来着手。一个方向是从 Linux 内核内部开始，直接修改其内核源代码，其典型代表是 Preempt_RT 实时补丁；另一个方向则是从 Linux 内核的外围开始，实现一个与 Linux 内核共存的实时内核，即采用双内核方法，其典型实现为 RTAI/Linux，即现在的 Xenomai。

因为 Xenomai 实时内核与 Linux 内核共存，Xenomai 实时内核小而精巧，能够很好地控制其中的代码质量。Xenomai 实时内核完成了基本的硬件抽象层、任务调度管理和进程间通信管理模块等，能够满足一些硬实时系统的需求。然而，其上的实时应用通常分为实时和非实时两部分来完成 ，实时部分必须使用 Xenomai 提供的特有的 API；非实时部分则可以使用 Linux 提供的系统调用。与 Preempt_RT 实时编程相比，Xenomai 编程实现更为困难，软件移植难度更大。

与双内核机制方案相比，Preempt_RT 实时补丁最大的优势在于它遵循 POSIX 标准，使用该补丁的实时系统应用程序和驱动程序与非实时系统的应用和驱动程序差异很小。因此，在使用该补丁的平台上做相应的开发比双内核机制的方案更容易。另外，该补丁与硬件平台相关性小，可移植性高。由于 Linux 内核过于庞大，有着较多关中断、关抢占代码，加上复杂的内存管理、调度器代码逻辑等众多不确定性因素，使得 Preempt_RT 虽然具有较好的软实时性，但在硬实时性方面有所欠缺。

## **什么是 Preempt_RT**

Preempt_RT 补丁开发始于 2005 年。之后由德国 OSADL 组织赞助，Ingo Molnar、Thomas Gleixner 和 Steven Rostedt 三人共同发起，旨在将 Linux 内核的最大线程切换延迟从无限制的毫秒数降低到数十微秒的有界值。2016 年以后成为 Linux 基金会下属合作项目。目前 Preempt_RT 的赞助者来自 ARM、BMW、CIP、ELISA、Intel、National Instruments、OSADL、RedHat 和 Texas Instruments 等。经过 Preempt_RT 和 Linux 内核工程师在抢占、实时性方面的努力，Linux 内核的抢占延迟降低了几个数量级，使其能够与商业实时操作系统竞争。业界知名的 MontaVista Linux、WindRiver Linux、TimeSys Linux 都有 RT 补丁的身影。像 RTJVM、RTKVM、RTDocker、RTAndroid 等曾经出现过的 Preempt_RT 衍生用例，响应速度都有着不同程度的提升。

多年来，该补丁的许多部分已被纳入主线 Linux，包括高分辨率计时器（2.6.16）、优先级继承（2.6.18）、可抢占的 RCU（2.6.25）、内核互斥量和线程中断处理程序（2.6.30）、完全 Tickless 机制（3.10）、DL 调度器（EDF 调度算法）（3.14）、实时抢占锁（5.15）。然而，该补丁的核心部分仍然在主线之外。从近几年的 Preempt_RT 补丁来看，当前的主要工作不是开发新功能，而是专注于增量式引入主线和特定架构的支持。

当前 openEuler 22.03 LTS 主线内核版本为 Linux Kernel 5.10，有 180 把锁无法抢占，其中 8 把锁在 RT 补丁中强制修改成无法抢占。在最新的 5.17 内核中，Preempt_RT 补丁大小为 265KB，有 189 把锁仍然无法抢占，RT 补丁不再强制修改锁为无法抢占。

## **当前 Preempt_RT 主要特性**

- 抢占式临界区
- 抢占式中断处理
- 抢占式中断禁止代码序列
- 内核自旋锁和信号量的优先级继承
- 递延操作
- 降低延迟的措施

### **抢占式临界区**

在PREEMPT_RT中，普通的自旋锁（spinlock_t and rwlock_t）是抢占式的，RCU读取侧临界区（(rcu_read_lock() 和rcu_read_unlock()）也是一样的。信号量临界区是可抢占的，他们已经存在于可抢占和非抢占内核中。这种可抢占性意思是可以阻止获取自旋锁，也就是在可抢占或中断禁用的情况下获取自旋锁是非法的（这个原则的一个例外就是变体_trylock，只要不是在密集信号中重复调用）。这也意味着当使用spinlock_t的时候spin_lock_irqsave()不会禁用硬件中断。

在中断或抢占禁用的情况下要获取锁要做什么？用raw_spinlock_t而不是spinlock_t，调用spin_lock()的时候使用raw_spinlock_t。PREEMPT_RT包含一个宏集合，这样会让spin_lock（）调用的时候就像c++中的函数重载。当使用raw_spinlock_t的时候，就是传统的自旋锁。但是当使用spinlock_t，临界区就是可抢占的。当使用raw_spinlock_t时，各种_irq原语（例如spin_lock_irqsave（））会禁用硬件中断，而在使用spinlock_t时不会禁用硬件中断。但是，使用raw_spinlock_t（及其对应的rwlock_t，raw_rwlock_t）应该是例外，而不是常规使用。在一些底层区域比如调度，特定的架构代码和RCU，是不需要这些原始锁的。

由于临界区可以被抢占，就不能依赖单个CPU上给定的临界区，因为可能会移到其他CPU上。所以，当你在临界区使用per-CPU变量时，必须单独处理抢占的可能性。因为spinlock_t和rwlock_t不再具有这个功能。

**可以通过以下两种方式实现：**

1. 显示禁用中断，或者通过调用get_cpu_var(), preempt_disable()，或者禁掉硬件中断。
2. 使用per-CPU锁来保护per-CPU变量，可以通过使用新的DEFINE_PER_CPU_LOCKED()原语。

由于spin_lock可以睡眠，所以会增加一个额外的任务状态。思考一下下面的代码序列：

```
spin_lock(&mylock1);
current->state=TASK_UNINTERRUPTIBLE;
spin_lock(&mylock2); // [*]
blah();
spin_unlock(&mylock2);
spin_unlock(&mylock1);
```

由于第二个spin_lock()调用可以睡眠，所以有可能会改变current-state的值，有可能使函数blah()产生令人惊讶的结果。在这种情况下，调度程序可以使用新的TASK_RUNNING_MUTEX位来保留current-state之前的值。尽管生成的环境有点陌生，但是通过少量的代码改动就实现了临界区抢占，并且PREEMPT_RT, PREEMPT和 non-PREEMPT三个配置项都是用相同的代码。

### **抢占式中断处理**

在PREEMPT_RT环境中几乎所有的进程上下文都有中断处理。虽然任何标为SA_NODELAY的中断都可以在其上下文中运行，但是仅在fpu_irq, irq0, irq2和lpptest指定了SA_NODELAY。其中，只有irq0(per-CPU计时器中断)可以正常使用。fpu-irq是用于浮点协处理器中断，而lpptest是用于中断等待时间基准测试。注意软件计时器(add_timer())不在硬件上下文中运行。它是运行在进程上下文中，并且是完全抢占式的。

注意不要轻易使用SA_NODELAY，因为它会大大降低中断和调度延迟。Per-CPU计时器中断之所以符合条件，是因为它与调度程序和其他核心内核组件紧密相关。此外，在写SA_NODELAY中断处理代码的时候必须要非常谨慎，否则很容易出现崩溃和死锁。

由于per-CPU计时器中断运行在硬件中断上下文中，因此任何和进程上下文代码共享的锁必须是原始自旋锁(raw_spinlock_t 或 raw_rwlock_t)。并且，从进程上下文获取时，必须使用_irq变体，比如spin_lock_irqsave()。另外，当进程上下文代码访问每个和SA_NODELAY中断处理程序共享的per-CPU变量的时候，一般上要禁用硬件中断。

### **抢占式“中断禁用”代码序列**

抢占式中断禁用代码序列的概念从术语上理解似乎是矛盾的，但是牢记PREEMPT_RT原理很重要。原理就是要依靠Linux内核的SMP功能来处理和中断处理程序的竞争。大多数中断处理程序都运行在进程上下文中。任何与中断处理程序有交互的代码都要准备处理在其他CPU上同时运行的该中断处理程序。

因此，spin_lock_irqsave()和相关的原语不需要禁用抢占。之所以安全的原因是，即使中断处理程序运行，即使它抢占了拥有spinlock_t的代码，但是在试图获取spinlock_t的时候会立即阻塞。临界区依旧会被保留。

但是，local_irq_save()依旧禁用抢占，因为没有任何锁依赖它。因此使用锁而不是local_irq_save()可以降低调度延迟，但是以这种方式替换锁会降低SMP性能，因此要小心。

需要和SA_NODELAY中断交互的代码不能使用local_irq_save()，因为它没用禁用硬件中断。相反，应该使用raw_local_irq_save()，类似的，当需要和SA_NODELAY中断处理程序交互的时候，需要使用原始自旋锁（raw_spinlock_t, raw_rwlock_t 和raw_seqlock_t）。但是原始自旋锁和原始中断禁用不应该在一些底层区域，如调度程序，架构依赖代码和RCU之外使用。

### **内核自旋锁和信号量的优先级继承**

实时程序员会经常担心优先级倒置，这可能会发生一下几种情况：

- 低优先级任务A获取资源，比如获取锁
- 中优先级任务B开始执行CPU绑定，抢占低优先级任务A
- 高优先级任务C试图获取低优先任务A持有的锁，但是被阻塞了。因为中优先级任务B已经抢占了低优先级任务A

这种优先级倒置可以无限期地延迟高优先级任务。有两种方式可以解决这个问题：（1）抑制抢占；（2）优先级继承。第一种情况，由于没有抢占，所以任务B不能抢占任务A，从而阻止优先级反转的发生。这种方式在PREEMPT内核中用于自旋锁，但不用于信号量。抑制抢占对于信号量来说是没有意义的。因为持有一个信号量的时候阻塞是合法的，即使没有抢占也会导致优先级反转。对于某些实时工作负载，自旋锁也不能抑制抢占，因为会对调度延迟造成影响。

优先级继承可以用在抢占抑制没有意义的场合。就是高优先级任务临时把优先级赠与持有关键锁的低优先级任务。优先级继承是可以传递的：在上面的例子中，如果更高优先级任务D试图获取高优先级任务C已经持有的第二把锁，任务C和A都将暂时提升为任务D的优先级。优先级提升的持续时间也受到严重限制：一旦低优先级任务A释放了锁，它会立刻失去临时提升的优先级，把锁交给任务C。

但是，任务C运行需要时间，很可能同时另一个更高优先级任务E来试图获取锁。如果发生这种情况，任务E会从任务C那里偷到锁。这样是合法的，因为任务C还没有运行，因此实际上它并没有获取锁。另一方面，如果任务C在任务E试图获取锁之前已经运行，那么任务E是无法偷锁的，必须等待任务C释放锁，可能会提高任务C的优先级以加快处理速度。

另外，在某些情况下会长时间保持锁定。其中一些增加了“抢占点”，以便锁持有者在某些其他任务需要时丢弃该锁。

事实证明，读写优先级继承特别成问题。因此，尽管任务可以递归获取，但Preempt_RT可以通过一次只允许一个任务获取读写锁或信号量来简化这个为题。尽管限制了可扩展性，但这让优先级继承实现成为可能。

此外，在某些情况下，信号量不需要优先级继承，比如当信号量用于事件机制而不是锁的时候。compat_semaphore 和compat_rw_semaphore变体可以用于这种情况。很多信号量原语（up(), down()等）可用于compat_semaphore 和compat_rw_semaphore。相同的，读写信号量原语（up_read(), down_write()等）可用于compat_rw_semaphore 和rw_semaphore。

总结一下，优先级继承可以防止优先级反转，允许高优先级任务及时获取锁和信号量，即使这些锁和信号量被低优先级任务持有。PREEMPT_RT的优先级继承具有传递性且能够及时移除，并且具有当高优先级任务突然需要低优先任务持有的锁时，处理这种情况的灵活性。当信号量用于事件机制的时候，compat_semaphore 和compat_rw_semaphore可以避免优先级继承。

### **递延操作**

由于spin_lock()现在可以休眠，所以当抢占或中断被禁用的时候，调用它就不再合法了。在一些情况下，可以通过递延操作要求spin_lock()等到抢占被重新启用的时候来解决这个问题。

- 当合法获取task_struct中的spinlock_t alloc_lock是，可以将put_task_struct（）放到put_task_struct_delayed()队列中，以便延迟运行。
- 把mmdrop()放到mmdrop_delayed()队列中，延迟运行。
- TIF_NEED_RESCHED_DELAYED重新调度，不过需要等到进程返回到用户空间，或者等到下一个preempt_check_resched_delayed（）。无论哪种方式，关键点在于避免在唤醒高优先级任务直到当前任务未锁定之前无法取得进展的情况下进行不必要的抢占。没有TIF_NEED_RESCHED_DELAYED，高优先级任务会立刻抢占低优先级任务，只能被快速阻塞等待低优先级任务持有的锁。

解决方案是在spin_unlock()之后增加wake_up()去替代wake_up_process_sync（）。如果唤醒的进程抢占当前进程，通过TIF_NEED_RESCHED_DELAYED，唤醒操作会被延迟。

在所有这些情况下，解决方案是将操作推迟到可以更安全或更方便地执行该操作。

### **降低延迟的操作**

在PREEMPT_RT中的一些改变，主要目的是降低调度或中断延迟。

第一种改变是引入x86 MMX/SSE硬件。这个硬件在内核中处理中断禁用。某些情况下意味着等待直到MMX/SSE指令完成。一些MMX/SSE指令没有问题，但是有些指令要花很长时间，所以PREEMPT_RT拒绝使用这些很慢的指令。

第二个改变是使用per-CPU变量用于板坯分配器，以代替之前随意的中断禁用。

## **PREEMPT_RT原语总结**

这个章节总结PREEMPT_RT增加的原语列表或者原来的行为几乎被PREEMPT_RT改变的原语列表。

### **锁原语**

- **spinlock_t**

    关键临界区是抢占式的。_irq操作没有禁用硬件中断。优先级继承用来防止优先级反转。rt_mutex在PREEMPT_RT用来实现spinlock_t（包括rwlock_t, struct semaphore和struct rw_semaphore）

- **raw_spinlock_t**

    提供spinlock_t原有功能的的特定变种，所以临界区是非抢占的，_irq真的禁用了硬件中断。需要注意的是在raw_spinlock_t上应该使用正常原语(比如spin_lock())。也就是，除了特定架构或者底层调度与同步原语外禁止使用raw_spinlock_t。误用raw_spinlock_t会破坏PREEMPT_RT的实时性。

- **rwlock_t**

    关键临界区是抢占式的。_irq操作没有禁用硬件中断。优先级继承用来防止优先级反转。为了保持优先级继承窒息的复杂度，每个任务只允许读取/获取一次给定的rwlock_t，即使这个任务会递归读取/获取rwlock_t。

- **RW_LOCK_UNLOCKED(mylock)**

    RW_LOCK_UNLOCKED宏根据优先级继承的要求蒋锁自身作为参数。但是，这样使用的话，与抢占和非抢占的内核都是不兼容的。使用RW_LOCK_UNLOCKED因此要改为DEFINE_RWLOCK()。

- **raw_rwlock_t**

    提供rwlock_t原有功能的特定变种，所以临界区是非抢占的，_irq真的禁用了硬件中断。需要注意的是在raw_rwlock_t上应该使用正常原语(比如read_lock ())。也就是，除了特定架构或者底层调度与同步原语外禁止使用raw_rwlock_t。误用raw_rwlock_t会破坏PREEMPT_RT的实时性。

- **seqlock_t**

    临界区是抢占式的。更新操作已经使用优先级继承。（读取操作不需要优先级继承因为seqlock_t读者不能阻塞写操作）

- **SEQLOCK_UNLOCKED(name)**

    SEQLOCK_UNLOCKED宏根据优先级继承的要求将锁自身作为参数。但是，这样使用与抢占和非抢占的内核都是不兼容的。使用SEQLOCK_UNLOCKED因此要改为DECLARE_SEQLOCK ()。注意DECLARE_SEQLOCK()定义并初始化seqlock_t。

- **struct semaphore**

    semaphore受优先级继承的约束。

- **down_trylock()**

    这个原理用于调度，因此不能在禁用硬件中断和禁用抢占的情况下使用。但是几乎所有的中断都需要在启用了抢占和中断的进程上下文中允许，所以这个限制目前没有任何影响。

- **struct compat_semaphore**

    结构体semaphore的变种，不受优先级继承的约束。这个结构体在事件机制下非常有用，对睡眠锁没用。

- **struct rw_semaphore**

    结构体rw_semaphore受继承优先级约束，并且一个任务每次只能读取一次。但是，这个任务可以递归的读取rw_semaphore.

- **struct compat_rw_semaphore**

    结构体rw_semaphore的变种，不受优先级继承的约束。这个结构体在事件机制下非常有用，对睡眠锁没用。

### **Per-CPU 变量**

- **DEFINE_PER_CPU_LOCKED(type, name)**

- **DECLARE_PER_CPU_LOCKED(type, name)**

    定义/声明有指定类型和名字的per-CPU变量，但是也要定义/声明相应的spinlock_t。如果有一组per-CPU变量需要回旋锁的保护，要把它们分组到一个结构体中。

- **get_per_cpu_locked(var, cpu)**

    返回指定CPU的指定的per-CPU变量，但是只能在获取相应的自旋锁之后。

- **put_per_cpu_locked(var, cpu)**

    释放指定CPU相应的自旋锁给指定的per-CPU变量。

- **per_cpu_lock(var, cpu)**

    释放指定CPU相应的自旋锁给指定的per-CPU变量，但是是作为左值。当调用的函数的参数是一个将要释放的自旋锁试非常有用。

- **per_cpu_locked(var, cpu)**

    将指定 CPU 的指定 per-CPU 变量作为左值返回，但不获取锁，大概是因为已经获取了锁但需要获取对该变量的另一个引用。或者可能是因为正在对变量进行 RCU 读取端引用，因此不需要获取锁。

### **中断处理**

- **SA_NODELAY**

    在结构体irqaction使用，指定直接调用在硬件中断上下文中相应的中断处理程序，而不是移交线程irq。函数redirect_hardirq()负责唤醒，在do_irqd()函数中可以找到中断处理循环。

    注意：SA_NODELAY不能用于正常的设备中断。

    1. 会降低中断和调度延迟

    2. SA_NODELAY中断处理程序的编码和维护比普通的中断处理程序要困难。只在低级别的中断或需要极端实时延迟的硬件中断使用SA_NODELAY

- **local_irq_enable()**

- **local_irq_disable()**

- **local_irq_save(flags)**

- **local_irq_restore(flags)**

- **irqs_disabled()**

- **irqs_disabled_flags()**

- **local_save_flags(flags)**

    local_irq*() 函数实际上并没有禁用硬件中断，它们只是禁用了抢占。这些适用于普通中断，但不适用于 SA_NODELAY 中断处理程序。

    然而，对于 PREEMPT_RT 环境，使用锁（可能是per-CPU 的锁）而不是这些函数通常会更好——但也 要考虑对使用非 抢占内核的 SMP 机器的影响！

- **raw_local_irq_enable()**

- **raw_local_irq_disable()**

- **raw_local_irq_save(flags)**

- **raw_local_irq_restore(flags)**

- **raw_irqs_disabled()**

- **raw_irqs_disabled_flags()**

- **raw_local_save_flags(flags)**

    这些函数禁用了硬件中断，因此适用于SA_NODELAY中断。这些函数特定只在低级代码中使用，例如调度程序、同步原语等。注意，在 raw_local_irq*() 的影响下，无法获得正常的 spinlock_t 锁。

### **其他项**

- **wait_for_timer()**

    等待指定的计时器到期。这是必需的，因为定时器在 PREEMPT_RT 环境中运行，因此可以被抢占，也可以阻塞，比如如在 spinlock_t 获取期间。

- **smp_send_reschedule_allbutself()**

    将重新调度 IPI 发送到所有其他 CPU。这在调度器中用于快速找到另一个 CPU 来运行新唤醒的高优先级实时任务，但没有足够高的优先级在当前 CPU 上运行。这种能力对于进行实时所需的高效全局调度是必要的。非实时任务继续以传统方式按 CPU 进行调度，牺牲一些优先级的准确性以提高效率和可扩展性。

- **INIT_FS(name)**

    将变量的名称作为参数，以便内部 rwlock_t 可以正确初始化（考虑到优先级继承的需要）

- **local_irq_disable_nort()**

- **local_irq_enable_nort()**

- **local_irq_save_nort(flags)**

- **local_irq_restore_nort(flags)**

- **spin_lock_nort(lock)**

- **spin_unlock_nort(lock)**

- **spin_lock_bh_nort(lock)**

- **spin_unlock_bh_nort(lock)**

- **BUG_ON_NONRT()**

- **WARN_ON_NONRT()**

    这些在 PREEMPT_RT 中什么都不做（或几乎什么都不做），但在其他环境中具有正常效果。这些原语不应在低级代码之外使用（例如，在调度程序、同步原语或特定于体系结构的代码中）。

- **spin_lock_rt(lock)**

- **spin_unlock_rt(lock)**

- **in_atomic_rt()**

- **BUG_ON_RT()**

- **WARN_ON_RT()**

    这些在 PREEMPT_RT 中有正常的效果，但在其他环境中什么也不做。同样，这些原语不应在低级代码之外使用（例如，在调度程序、同步原语或特定于体系结构的代码中）。

- **smp_processor_id_rt(cpu)**

    在 PREEMPT_RT 环境中返回“cpu”，但在其他环境中的作用与 smp_processor_id() 相同。这仅用于slab分配器。

### **PREEMPT_RT配置选项**

**High-Level Preemption-Option Selection**

- PREEMPT_NONE：为服务器操作系统选择传统的非抢占内核
- PREEMPT_VOLUNTARY：启动自愿抢占点，但是不能批发内核抢占。这个主要是桌面操作系统使用
- PREEMPT_DESKTOP：启用自愿抢占点以及非关键部分抢占 。适用于低延迟桌面操作系统使用。
- PREEMPT_RT：启用完全抢占，包括临界区。

**Feature-Selection Configuration Options**

- PREEMPT：启用非临界区内核抢占
- PREEMPT_BKL ：大内核锁临界区抢占.
- PREEMPT_HARDIRQS：硬中断在进程上下文中允许，从而可抢断。但是标记为SA_NODELAY的irqs继续在硬件中断上下文中进行。
- PREEMPT_RCU ：RCU读侧临界区可抢占。
- PREEMPT_SOFTIRQS ：软中断在进程上下文中进行，从而可抢占。

### **调试配置项**

**有些可能已经发生了变化，但是可以了解下PREEMPT_RT可以提供的调试种类：**

- CRITICAL_PREEMPT_TIMING: 测量内核在禁用抢占的情况下花费的最长时间
- CRITICAL_IRQSOFF_TIMING ：测量内核在禁用硬件中断请求的情况下花费的最长事件。
- DEBUG_IRQ_FLAGS：内核验证spin_unlock_irqrestore()和其他类似原语的“flg“参数。
- DEBUG_RT_LOCKING_MODE：启用从可抢占到不可抢占的自旋锁的运行事件切换。对于想要评估 PREEMPT_RT 机制开销的内核开发人员很有用。
- DETECT_SOFTLOCKUP：内核在转储任何进程当前堆栈跟踪，超过10秒不需要内核重新调度。
- LATENCY_TRACE ：记录表示长延迟事件的函数调用跟踪。这些跟踪可以通过 /proc/latency_trace 从内核中读出。可以通过/proc/sys/kernel/preempt_thresh 过滤掉低延迟跟踪。这个选项在跟踪过度低延时非常有用。
- LPPTEST：执行基于并行端口的延迟测量的设备驱动程序，使用 scripts/testlpp.c 实际运行此测试
- PRINTK_IGNORE_LOGLEVEL ：-all-printk() 消息被转储到控制台。通常不是什么好方法，但在其他调试工具失败时很有帮助。
- RT_DEADLOCK_DETECT：发现死锁循环。
- RTC_HISTOGRAM ：使用 /dev/rtc 为应用程序生成延迟直方图数据。
- WAKEUP_TIMING ：测量从高优先级线程被唤醒到它实际开始运行的最长时间（以微秒为单位）。结果是从 /proc/sys/kernel/wakeup_timing 访问的。并且可以通过 echo 0 > /proc/sys/kernel/preempt_max_latency 重新启动测试

## **部署方法**

### 二进制部署

二进制部署可以安装 openEuler 22.03 LTS 官方源中 rpm 包，需要 root 权限，命令如下：

```
# yum install kernel-rt
```

完成安装后重启设备，在 GRUB 引导界面选择 Preempt_RT 内核`openEuler (5.10.0-60.18.0.rt62.52.oe2203.aarch64) 22.03 LTS`即可。启动后查看内核，即完成 openEuler 22.03 LTS Preempt_RT 二进制部署。

```
# uname -r
5.10.0-60.18.0.rt62.52.oe2203.aarch64
```

### 获取源码

openEuler 22.03 LTS `kernel-rt`源码可以直接从官方源获取，查询命令如下：

```
# yum search kernel-rt
...
kernel-rt.src : Linux Kernel
```

若源里包含 `kernel-rt` 源码，则可使用如下方式下载并安装：

```
# yumdownloader --source kernel-rt.src
# rpm -ivh kernel-rt-5.10.0-60.18.0.rt62.52.oe2203.src.rpm && cd ~/rpmbuild
```

源码包也可以从下面的地址中直接获取：

 https://repo.huaweicloud.com/openeuler/openEuler-22.03-LTS/source/Packages/kernel-rt-5.10.0-60.18.0.rt62.52.oe2203.src.rpm

源码目录树如下：

```
# tree
.
├── SOURCES
│   ├── cpupower.config
│   ├── cpupower.service
│   ├── extra_certificates
│   ├── kernel.tar.gz
│   ├── mkgrub-menu-aarch64.sh
│   ├── patch-5.10.0-60.10.0-rt62_openeuler_defconfig.patch
│   ├── patch-5.10.0-60.10.0-rt62.patch
│   ├── pubring.gpg
│   ├── sign-modules
│   └── x509.genkey
└── SPECS
    └── kernel-rt.spec
```

表1：kernel-rt源码包主要文件

| 文件                                                | 说明                         |
| :-------------------------------------------------- | :--------------------------- |
| kernel.tar.gz                                       | 内核源码                     |
| patch-5.10.0-60.10.0-rt62_openeuler_defconfig.patch | openeuler_defconfig 文件补丁 |
| patch-5.10.0-60.10.0-rt62.patch                     | Preempt_RT 补丁              |
| kernel-rt.spec                                      | Preempt_RT 内核 spec 文件    |

### 源码部署

源码获取后，复制以下文件到自定义目录：

```
# ll
total 186M
-rw-r--r--. 1 root root 185M Apr  2 14:27 kernel.tar.gz
-rw-r--r--. 1 root root 4.5K Apr  2 14:27 patch-5.10.0-60.10.0-rt62_openeuler_defconfig.patch
-rw-r--r--. 1 root root 773K Apr  2 14:27 patch-5.10.0-60.10.0-rt62.patch
```

补丁合入步骤如下：

```
# tar -xzf kernel.tar.gz && cd kernel
# patch -p1 < ../patch-5.10.0-60.10.0-rt62.patch
# patch -p1 < ../patch-5.10.0-60.10.0-rt62_openeuler_defconfig.patch
```

源码编译安装：

```
# make openeuler_defconfig && make -j`nproc`
# make modules_install && make install
# grub2-mkconfig -o $GRUB_CONFIG_PATH
```

## 嵌入式系统部署方法

嵌入式部署 Preempt_RT 方法参见：

https://openeuler.gitee.io/yocto-meta-openeuler/features/preempt_rt.html

## 实时性能测试

表2：缩略语

| 缩略语     | 英文全名        | 说明                                                         |
| :--------- | :-------------- | :----------------------------------------------------------- |
| RT 内核    | Realtime kernel | 实时内核，本文指 openEuler 22.03 LTS 发布的`kernel-rt`内核   |
| 非 RT 内核 | /               | 非实时内核，实时内核，本文指 openEuler 22.03 LTS 发布的`kernel`内核 |

### 测试环境

表3：测试软件环境

| 版本名称                             | 来源                       |
| :----------------------------------- | :------------------------- |
| openEuler 22.03 LTS `kernel` 内核    | openEuler 22.03 LTS 官方源 |
| openEuler 22.03 LTS `kernel-rt` 内核 | openEuler 22.03 LTS 官方源 |

表4：测试硬件环境

| 硬件型号   | 硬件配置信息                                                 | 备注   |
| :--------- | :----------------------------------------------------------- | :----- |
| 飞腾 D2000 | CPU：8 核 内存：8GB 存储设备：SSD                            | 台式机 |
| 树莓派 4B  | CPU:Cortex-A72 * 4 内存：8GB 存储设备：SanDisk Ultra 16GB micro SD | 开发板 |
| 飞腾 2000  | CPU：4 核 内存：16GB 存储设备：SSD                           | 台式机 |

表5：测试软件

| 测试软件              | 功能                                                         | 软件版本 |
| :-------------------- | :----------------------------------------------------------- | :------- |
| rt-test（cyclictest） | 通过 cyclictest 工具，每项测试 1000 万次，输出平均延迟(Avg)和最大延迟(MAX) | 1.00     |
| stress                | 压力测试工具，用于模拟测试 CPU 负载，内存负载，IO 负载等     | 1.0.4    |
| iperf3                | 网络测试工具，用于模拟测试网络负载                           | 3.6      |
| memtester             | 内存测试工具，用于模拟测试内存负载                           | 4.5.1    |
| shell 脚本            | 用于轮询测试，测试信息的收集整理                             | —        |

### 测试结果

基于上述硬件测试环境，在 CPU 隔离、空负载、CPU 负载、内存负载、IO 负载和网卡负载等不同条件下的测试数据：

表6：详细测试结果(单位微秒)

![图片](https://mmbiz.qpic.cn/mmbiz_png/A0h5yD51CMYPvic3ESZ0PVHibxd5IricESRzbhozU7oAibVbNBH3SjGjOrD9FokJJeHEelSfqz65XfvFZMwR0icpnBA/640?wx_fmt=png&wxfrom=5&wx_lazy=1&wx_co=1)

**「归纳如下：」**

1. 通过表 6 数据可以判断，在五种负载情况下并且 CPU 不隔离，RT 内核比非 RT 内核实时性要强。非 RT 内核与 RT 内核在 CPU 不隔离情况下，五种负载对应峰值的比值如表 7(比值数据越大表明非 RT 内核实时性越差)：

表7：非RT内核与RT的内核峰值延迟比值数据表

| 平台       | 空负载 | CPU 负载 | 内存负载 | IO 负载 | 网卡负载 |
| :--------- | :----- | :------- | :------- | :------ | :------- |
| 飞腾 D2000 | 22.7   | 117.1    | 51.0     | 184.6   | 2.9      |
| 树莓派 4B  | 3.6    | 2.9      | 4.3      | 0.8     | 1.5      |
| 飞腾 2000  | 5.4    | 4.3      | 5.3      | 34.7    | 10.6     |

**「以上数据表明，RT 内核的峰值延迟普遍要优于非 RT 内核。」**

1. 结合四种设备的峰值延迟来看，CPU 负载对实时性影响一般小于 IO 和内存负载，而网卡负载影响最小。四种设备在两种内核下，CPU、内存、IO 和网卡负载与空负载比值如表 8(比值越小越稳定)：

表8：负载与空负载峰值延迟比值表

| 平台                   | CPU 负载 | 内存负载 | IO 负载 | 网卡负载 |
| :--------------------- | :------- | :------- | :------ | :------- |
| 飞腾 D2000(非 RT 内核) | 5.2      | 43.1     | 212.8   | 2.7      |
| 树莓派 4B(非 RT 内核)  | 0.8      | 2.7      | 1.0     | 0.7      |
| 飞腾 2000(非 RT 内核)  | 0.8      | 18       | 26.8    | 1.9      |
| 飞腾 D2000(RT 内核)    | 1.0      | 19.2     | 26.2    | 20.6     |
| 树莓派 4B(RT 内核)     | 0.9      | 1.2      | 4.2     | 1.0      |
| 飞腾 2000(RT 内核)     | 1.0      | 2.2      | 4.5     | 1.7      |

**「表 8 各项数据表明，RT 内核在负载情况下，实时性较为稳定。」**

**「为确保 Cyclictest 测试的有效性，经过飞腾 2000 平台空载测试 2 天，最大延迟为 58 微秒。」**

## 实时性对系统影响测试

### 测试环境

表9：测试软件环境

| 版本名称                             | 来源                       |
| :----------------------------------- | :------------------------- |
| openEuler 22.03 LTS `kernel` 内核    | openEuler 22.03 LTS 官方源 |
| openEuler 22.03 LTS `kernel-rt` 内核 | openEuler 22.03 LTS 官方源 |

表10：硬件测试环境

| 硬件型号    | 硬件配置信息                       | 备注   |
| :---------- | :--------------------------------- | :----- |
| 飞腾 D2000  | CPU：8 核 内存：16GB 存储设备：SSD | 台式机 |
| 飞腾 2000/4 | CPU：4 核 内存：16GB 存储设备：SSD | 台式机 |

表11：测试工具

| 测试软件              | 功能                                                         | 版本    |
| :-------------------- | :----------------------------------------------------------- | :------ |
| unixbench             | 系统的基准测试工具，可用于测试 CPU、内存、磁盘等。测试结果与硬件、系统、开发库、编译器等相关。 | 5.1.3   |
| lmbench               | 是一套简易可移植的，符合 ANSI/C 标准为 UNIX/POSIX 而制定的微型测评工具。一般来说，它衡量两个关键特征：反应时间和带宽。Lmbench 旨在使系统开发者深入了解关键操作的基础成本。 | 3alpha4 |
| rt-test（cyclictest） | 通过 cyclictest 工具，每项测试 1000 万次，输出平均延迟(Avg)和最大延迟(MAX) | 1.00    |

### 测试结果

- 飞腾 D2000 平台 unixbench 测试结果

使用`unixbench`单个任务测试非 RT 内核空负载、RT 内核空负载、RT 内核负载 cyclictest(cyclictest -m -h 100 -q -i100 -t 1 -p 99 -n)，三种状态详细测试结果如下(表中“RT/非 RT”、“RT 负载/非 RT”为百分比值，数值越大说明 RT 内核性能越好)：

表12：单任务Unixbench测试结果

| 测试项                                | 非 RT 内核    | RT 内核       | RT 内核负载   | RT/非 RT       | RT 负载/非 RT  |
| :------------------------------------ | :------------ | :------------ | :------------ | :------------- | :------------- |
| Dhrystone 2 using register variables  | 24920250.9    | 24994936.3    | 25463306.6    | 100.30%        | 102.18%        |
| Double-Precision Whetstone            | 4043.3        | 4042.8        | 4042.9        | 99.99%         | 99.99%         |
| Execl Throughput                      | 2700.1        | 2112.1        | 2109.6        | 78.22%         | 78.13%         |
| File Copy 1024 bufsize 2000 maxblock  | 437294.1      | 307416.2      | 303652.3      | 70.30%         | 69.44%         |
| File Copy 256 bufsize 500 maxblocks   | 122072.4      | 88889.0       | 86090.9       | 72.82%         | 70.52%         |
| File Copy 4096 bufsize 8000 maxblocks | 995255.5      | 809771.5      | 774228.3      | 81.36%         | 77.79%         |
| Pipe Throughput                       | 612119.9      | 487314.9      | 482060.0      | 79.61%         | 78.75%         |
| Pipe-based Context Switching          | 79151.2       | 65953.5       | 65399.0       | 83.33%         | 82.63%         |
| Process Creation                      | 5098.4        | 3481.7        | 3367.9        | 68.29%         | 66.06%         |
| Shell Scripts (1 concurrent)          | 3907.2        | 3311.8        | 3264.1        | 84.76%         | 83.54%         |
| Shell Scripts (8 concurrent)          | 1724.2        | 1199.9        | 1187.6        | 69.59%         | 68.88%         |
| System Call Overhead                  | 478285.9      | 436596.3      | 434507.4      | 91.28%         | 90.85%         |
| **「System Benchmarks Index Score」** | **「773.4」** | **「626.4」** | **「618.5」** | **「80.99%」** | **「79.97%」** |

使用`unixbench`多任务测试非 RT 内核空负载、RT 内核空负载、RT 内核负载 cyclictest(cyclictest -m -h 100 -q -i100 -t 1 -p 99 -n)，三种状态详细测试结果如下(表中“RT/非 RT”、“RT 负载/非 RT”为百分比值，数值越大说明 RT 内核性能越好)：

表13：多任务Unixbench测试结果

| 测试项                                | 非 RT 内核     | RT 内核        | RT 内核负载    | RT/非 RT       | RT 负载/非 RT  |
| :------------------------------------ | :------------- | :------------- | :------------- | :------------- | :------------- |
| Dhrystone 2 using register variables  | 199461755.8    | 199159490.6    | 195978301.9    | 99.85%         | 98.25%         |
| Double-Precision Whetstone            | 32216.4        | 32308.6        | 32094.1        | 100.29%        | 99.62%         |
| Execl Throughput                      | 14832.9        | 9786.4         | 9375.0         | 65.98%         | 63.20%         |
| File Copy 1024 bufsize 2000 maxblock  | 924225.9       | 107564.5       | 104520.3       | 11.64%         | 11.31%         |
| File Copy 256 bufsize 500 maxblocks   | 253687.9       | 27474.4        | 26157.9        | 10.83%         | 10.31%         |
| File Copy 4096 bufsize 8000 maxblocks | 2523753.4      | 415702.5       | 395431.5       | 16.47%         | 15.67%         |
| Pipe Throughput                       | 4848867.9      | 3771186.3      | 3822723.4      | 77.77%         | 78.84%         |
| Pipe-based Context Switching          | 657475.9       | 526984.6       | 522867.1       | 80.15%         | 79.53%         |
| Process Creation                      | 29117.5        | 11881.7        | 11580.0        | 40.81%         | 39.77%         |
| Shell Scripts (1 concurrent)          | 17309.7        | 8265.0         | 8199.6         | 47.75%         | 47.37%         |
| Shell Scripts (8 concurrent)          | 2308.1         | 957.1          | 937.3          | 41.47%         | 40.61%         |
| System Call Overhead                  | 2928882.1      | 2765649.3      | 2744875.5      | 94.43%         | 93.72%         |
| **「System Benchmarks Index Score」** | **「3406.4」** | **「1525.8」** | **「1494.4」** | **「44.79%」** | **「43.87%」** |

- 飞腾 D2000 平台 lmbench 测试结果

    使用`lmbench`测试非 RT 内核空负载、RT 内核空负载、RT 内核负载 cyclictest(cyclictest -m -h 100 -q -i100 -t 1 -p 99 -n)，三种状态详细，测试十次取平均值，结果如下：

    表14：多任务Lmbench测试结果

    ![图片](https://mmbiz.qpic.cn/mmbiz_png/A0h5yD51CMYPvic3ESZ0PVHibxd5IricESRmnNPynJqmEYic0ibGNLnJsTY7pZTow3Jiaia3XfsrsuYeM3Y4q3WIHAwqw/640?wx_fmt=png&wxfrom=5&wx_lazy=1&wx_co=1)

- 飞腾 2000 平台测试结果

    飞腾 2000 平台测试结果与飞腾 D2000 平台测试结果相似度较高，具体数据不在此处列出。

## 测试结论

**「Preempt_RT 补丁可以有效提高系统实时性，且在多种负载场景下，实时性表现较为稳定。」**

**「Preempt_RT 补丁对本地通讯吞吐率有一定影响，主要提现为管道读写、文件拷贝，对系统调用延迟影响大多在 2 微秒以内。」**

## 后续工作

1. 跟随内核主线发布、维护 Preempt_RT 补丁
2. 研发实时性性能分析工具
3. 提升实时性
4. 提升吞吐率
5. 引入 RTLA、RTSL 机制等
6. 实时性最佳实践

## 主要参与者

特别感谢 Kernel SIG 组XieXiuQi、zhengzengkai，Embedded SIG 组wanming-hu，树莓派 SIG 组woqidaideshi，QA SIG 组suhang给予我们的帮助。

| 姓名   | Gitee ID      | 邮箱                     |
| :----- | :------------ | :----------------------- |
| 郭皓   | guohaocs2c    | guohao@kylinos.cn        |
| 马玉昆 | kylin-mayukun | mayukun@kylinos.cn       |
| 张远航 | zhangyh1992   | zhangyuanhang@kylinos.cn |

## **以上观点如有纰漏，请留言指正。**

