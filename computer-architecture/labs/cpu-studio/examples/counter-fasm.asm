; Linux x86-64, FASM. Build: fasm counter-fasm.asm counter
format ELF64 executable 3
entry _start
segment readable executable
_start:
    mov edi, 42
    inc edi
    call print_u32
    mov eax, 60
    xor edi, edi
    syscall

; EDI = unsigned 32-bit integer.
; Uses RAX, RCX, RDX, RSI, RDI, R8, R11. Keeps callee-saved registers.
print_u32:
    sub rsp, 24
    lea r8, [rsp + 23]
    mov byte [r8], 10
    mov eax, edi
    mov ecx, 10
.digits:
    xor edx, edx
    div ecx
    add dl, '0'
    dec r8
    mov [r8], dl
    test eax, eax
    jnz .digits

    lea rdx, [rsp + 24]
    sub rdx, r8
    mov rsi, r8
.write:
    mov eax, 1
    mov edi, 1
    syscall
    cmp rax, -4                 ; EINTR, retry this write
    je .write
    test rax, rax
    jle .failed
    add rsi, rax
    sub rdx, rax
    jnz .write
    add rsp, 24
    ret
.failed:
    mov eax, 60
    mov edi, 1
    syscall
