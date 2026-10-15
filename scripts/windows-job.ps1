# Each launch owns one Windows Job Object. Closing its non-inherited handle
# also terminates Python redirector children, search workers and native engines.
if (-not ('XiangqiProcessJob' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public sealed class XiangqiProcessJob : IDisposable {
    [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
        public long ProcessTime, JobTime;
        public uint Flags;
        public UIntPtr MinimumWorkingSet, MaximumWorkingSet;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)] struct IoCounters {
        public ulong ReadOperations, WriteOperations, OtherOperations;
        public ulong ReadBytes, WriteBytes, OtherBytes;
    }
    [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits {
        public BasicLimits Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern SafeFileHandle CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool SetInformationJobObject(SafeFileHandle job, int infoClass, ref ExtendedLimits info, uint length);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool AssignProcessToJobObject(SafeFileHandle job, IntPtr process);
    [StructLayout(LayoutKind.Sequential)] struct SecurityAttributes {
        public int Length;
        public IntPtr Descriptor;
        [MarshalAs(UnmanagedType.Bool)] public bool Inherit;
    }
    [StructLayout(LayoutKind.Sequential)] struct StartupInfo {
        public int Size;
        public IntPtr Reserved, Desktop, Title;
        public uint X, Y, XSize, YSize, XChars, YChars, Fill, Flags;
        public short ShowWindow, ReservedSize;
        public IntPtr ReservedData, Input, Output, Error;
    }
    [StructLayout(LayoutKind.Sequential)] struct ProcessInfo {
        public IntPtr Process, Thread;
        public uint ProcessId, ThreadId;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern SafeFileHandle CreateFile(string name, uint access, uint share, ref SecurityAttributes security, uint disposition, uint flags, IntPtr template);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool CreateProcess(string application, StringBuilder command, IntPtr processSecurity, IntPtr threadSecurity,
        bool inheritHandles, uint flags, IntPtr environment, string directory, ref StartupInfo startup, out ProcessInfo info);
    [DllImport("kernel32.dll", SetLastError=true)] static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool TerminateProcess(IntPtr process, uint code);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    readonly SafeFileHandle handle;
    public XiangqiProcessJob() {
        handle = CreateJobObject(IntPtr.Zero, null);
        if (handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
        var info = new ExtendedLimits();
        info.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (!SetInformationJobObject(handle, 9, ref info, (uint)Marshal.SizeOf(info))) {
            int error = Marshal.GetLastWin32Error(); handle.Dispose();
            throw new Win32Exception(error);
        }
    }
    public Process Start(string executable, string arguments, string directory, string stdout, string stderr) {
        var security = new SecurityAttributes();
        security.Length = Marshal.SizeOf(security); security.Inherit = true;
        using (var input = CreateFile("NUL", 0x80000000, 3, ref security, 3, 0, IntPtr.Zero))
        using (var output = CreateFile(stdout, 0x40000000, 3, ref security, 2, 0, IntPtr.Zero))
        using (var error = CreateFile(stderr, 0x40000000, 3, ref security, 2, 0, IntPtr.Zero)) {
            if (input.IsInvalid || output.IsInvalid || error.IsInvalid)
                throw new Win32Exception(Marshal.GetLastWin32Error());
            var startup = new StartupInfo(); startup.Size = Marshal.SizeOf(startup);
            startup.Flags = 0x100; // STARTF_USESTDHANDLES
            startup.Input = input.DangerousGetHandle(); startup.Output = output.DangerousGetHandle(); startup.Error = error.DangerousGetHandle();
            ProcessInfo info;
            // Assign before executing any code: even a fast Python redirector
            // cannot spawn a child outside the job during startup.
            if (!CreateProcess(executable, new StringBuilder("\"" + executable + "\" " + arguments),
                IntPtr.Zero, IntPtr.Zero, true, 0x08000004, IntPtr.Zero, directory, ref startup, out info))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            try {
                if (!AssignProcessToJobObject(handle, info.Process))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                var process = Process.GetProcessById((int)info.ProcessId);
                if (ResumeThread(info.Thread) == uint.MaxValue)
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                return process;
            } catch { TerminateProcess(info.Process, 1); throw; }
            finally { CloseHandle(info.Thread); CloseHandle(info.Process); }
        }
    }
    public void Dispose() { handle.Dispose(); }
}
'@
}
