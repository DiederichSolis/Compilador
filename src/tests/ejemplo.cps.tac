.func cuadrado(x) : integer
  .locals 0
f_cuadrado:
  t1 = %x * %x
  t0 = t1
  goto Lret0
Lret0:
  ret t0
.endfunc

.func max(a, b) : integer
  .locals 0
f_max:
  t1 = %a > %b
  ifFalse t1 goto Lelse1
  t0 = %a
  goto Lret0
  goto Lend2
Lelse1:
  t0 = %b
  goto Lret0
Lend2:
Lret0:
  ret t0
.endfunc

.func main() : void
  .locals 9
f_main:
  %i = #0
  %acc = #0
  %arr = #0
Lcond1:
  t1 = %i < %N
  ifFalse t1 goto Lend2
  t2 = aload %arr, %i
  param t2
  call %cuadrado, 1 -> t3
  t4 = %acc + t3
  %acc = t4
  t5 = %i + #1
  %i = t5
  goto Lcond1
Lend2:
  %j = #0
  t6 = %j < #3
  t7 = %j + #1
  t8 = %acc + %j
  %acc = t8
  t9 = %acc + %x
  %acc = t9
  t10 = %acc > #0
  %ok = #1
  ifFalse %ok goto Lelse3
  t11 = #"acc = " + %acc
  print t11
  goto Lend4
Lelse3:
  print #"acc = 0"
Lend4:
  %f = #3.0
  %g = #2.0
  t12 = %f / %g
  %h = t12
  param #10
  param #7
  call %max, 2 -> t13
  %m = t13
  t14 = %acc + %m
  %acc = t14
  t15 = #"final = " + %acc
  print t15
Lret0:
  ret
.endfunc