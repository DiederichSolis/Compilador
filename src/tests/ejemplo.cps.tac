.func cuadrado(x) : integer
  .locals 0
  t0 = %x * %x
.endfunc

.func max(a, b) : integer
  .locals 0
  t0 = %a > %b
  ifFalse t0 goto Lelse0
  goto Lend1
Lelse0:
Lend1:
.endfunc

.func main() : void
  .locals 0
  %i = #0
  %acc = #0
  %arr = #0
Lcond0:
  t0 = %i < %N
  ifFalse t0 goto Lend1
  t1 = aload %arr, %i
  param t1
  call %cuadrado, 1 -> t2
  t3 = %acc + t2
  %acc = t3
  t4 = %i + #1
  %i = t4
  goto Lcond0
Lend1:
  %j = #0
  t5 = %j < #3
  t6 = %j + #1
  t7 = %acc + %j
  %acc = t7
  t8 = %acc + %x
  %acc = t8
  t9 = %acc > #0
  %ok = #1
  ifFalse %ok goto Lelse2
  t10 = #"acc = " + %acc
  print t10
  goto Lend3
Lelse2:
  print #"acc = 0"
Lend3:
  %f = #3.0
  %g = #2.0
  t11 = %f / %g
  %h = t11
  param #10
  param #7
  call %max, 2 -> t12
  %m = t12
  t13 = %acc + %m
  %acc = t13
  t14 = #"final = " + %acc
  print t14
.endfunc