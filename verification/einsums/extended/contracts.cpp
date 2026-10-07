#include "proof_contract.hpp"
#include "kernels.hpp"
#include <string.h>
using namespace sage_cpp::contract;
uint64_t nondet_u64(); unsigned nondet_unsigned(); bool nondet_bool();
Metadata any_metadata() {
 Metadata a={nondet_bool(),nondet_u64(),nondet_u64(),nondet_u64(),nondet_u64(),nondet_bool()};return a;
}
bool valid(Metadata a) {
 if(!a.f64 || !a.dyadic || a.rank!=2 || a.rows==0 || a.cols==0 || a.rows>4 || a.cols>4)return false;
 return a.values==a.rows*a.cols;
}
void adapter_guard() {
 unsigned op=nondet_unsigned(); uint64_t arity=nondet_u64(); Metadata a=any_metadata(),b=any_metadata(); bool scalar=nondet_bool(),expected=false;
 switch(op) {
  case 0:case 3:expected=arity==1 && valid(a);break;
  case 5:expected=arity==1 && valid(a) && scalar;break;
  case 1:case 2:expected=arity==2 && valid(a) && valid(b) && a.rows==b.rows && a.cols==b.cols;break;
  case 4:expected=arity==2 && valid(a) && valid(b) && a.cols==b.rows;break;
 }
 __CPROVER_assert(route(op,arity,a,b,scalar)==expected,"adapter contract matches specification");
}
double value(uint64_t bits){double x;memcpy(&x,&bits,8);return x;}
uint64_t bits(double x){uint64_t b;memcpy(&b,&x,8);return b;}
void dyad_sound() {
 uint64_t b=nondet_u64();double x=value(b);
 if(dyad_bits(b)) {
   double scaled=x*8.; long long units=static_cast<long long>(scaled);
   __CPROVER_assert(finite_bits(b) && x>=-16. && x<=15.875 && scaled==static_cast<double>(units) && (b==0 || x!=0.),"dyadic eligibility matches specification");
 }
}
void dyad_complete() {
 signed char units;double x=static_cast<double>(units)/8.;
 __CPROVER_assert(dyad_bits(bits(x)),"all signed byte dyadics accepted");
}
void real_pivot() {
 uint64_t a=nondet_u64(),b=nondet_u64();__CPROVER_assume(finite_bits(a)&&finite_bits(b));
 double x=value(a),y=value(b);double ax=x<0.?-x:x,ay=y<0.?-y:y;
 __CPROVER_assert(greater_magnitude(a,b)==(ax>ay),"pivot order matches finite absolute values");
}
void frequency() {
 uint64_t n=nondet_u64(),i=nondet_u64();bool real=nondet_bool();
 __CPROVER_assume(n>0 && n<=0x7fffffffffffffffULL && i<n);
 int64_t expected=real || i<=(n-1)/2 ? static_cast<int64_t>(i):static_cast<int64_t>(i)-static_cast<int64_t>(n);
 __CPROVER_assert(frequency_bin(n,i,real)==expected,"frequency bin matches specification");
}
void layout_1x1() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,1,1);sage_cpp::transpose_kernel<uint64_t>(a,out,1,1);
 for(unsigned r=0;r<1;++r)for(unsigned c=0;c<1;++c){
  __CPROVER_assert(copy[r*1+c]==original[r*1+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*1+r]==original[r*1+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=1)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_1x2() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,1,2);sage_cpp::transpose_kernel<uint64_t>(a,out,1,2);
 for(unsigned r=0;r<1;++r)for(unsigned c=0;c<2;++c){
  __CPROVER_assert(copy[r*2+c]==original[r*2+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*1+r]==original[r*2+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=2)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_1x3() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,1,3);sage_cpp::transpose_kernel<uint64_t>(a,out,1,3);
 for(unsigned r=0;r<1;++r)for(unsigned c=0;c<3;++c){
  __CPROVER_assert(copy[r*3+c]==original[r*3+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*1+r]==original[r*3+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=3)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_1x4() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,1,4);sage_cpp::transpose_kernel<uint64_t>(a,out,1,4);
 for(unsigned r=0;r<1;++r)for(unsigned c=0;c<4;++c){
  __CPROVER_assert(copy[r*4+c]==original[r*4+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*1+r]==original[r*4+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=4)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_1x5() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,1,5);sage_cpp::transpose_kernel<uint64_t>(a,out,1,5);
 for(unsigned r=0;r<1;++r)for(unsigned c=0;c<5;++c){
  __CPROVER_assert(copy[r*5+c]==original[r*5+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*1+r]==original[r*5+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=5)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_1x6() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,1,6);sage_cpp::transpose_kernel<uint64_t>(a,out,1,6);
 for(unsigned r=0;r<1;++r)for(unsigned c=0;c<6;++c){
  __CPROVER_assert(copy[r*6+c]==original[r*6+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*1+r]==original[r*6+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=6)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_1x7() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,1,7);sage_cpp::transpose_kernel<uint64_t>(a,out,1,7);
 for(unsigned r=0;r<1;++r)for(unsigned c=0;c<7;++c){
  __CPROVER_assert(copy[r*7+c]==original[r*7+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*1+r]==original[r*7+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=7)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_1x8() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,1,8);sage_cpp::transpose_kernel<uint64_t>(a,out,1,8);
 for(unsigned r=0;r<1;++r)for(unsigned c=0;c<8;++c){
  __CPROVER_assert(copy[r*8+c]==original[r*8+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*1+r]==original[r*8+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=8)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_2x1() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,2,1);sage_cpp::transpose_kernel<uint64_t>(a,out,2,1);
 for(unsigned r=0;r<2;++r)for(unsigned c=0;c<1;++c){
  __CPROVER_assert(copy[r*1+c]==original[r*1+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*2+r]==original[r*1+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=2)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_2x2() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,2,2);sage_cpp::transpose_kernel<uint64_t>(a,out,2,2);
 for(unsigned r=0;r<2;++r)for(unsigned c=0;c<2;++c){
  __CPROVER_assert(copy[r*2+c]==original[r*2+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*2+r]==original[r*2+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=4)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_2x3() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,2,3);sage_cpp::transpose_kernel<uint64_t>(a,out,2,3);
 for(unsigned r=0;r<2;++r)for(unsigned c=0;c<3;++c){
  __CPROVER_assert(copy[r*3+c]==original[r*3+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*2+r]==original[r*3+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=6)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_2x4() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,2,4);sage_cpp::transpose_kernel<uint64_t>(a,out,2,4);
 for(unsigned r=0;r<2;++r)for(unsigned c=0;c<4;++c){
  __CPROVER_assert(copy[r*4+c]==original[r*4+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*2+r]==original[r*4+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=8)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_2x5() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,2,5);sage_cpp::transpose_kernel<uint64_t>(a,out,2,5);
 for(unsigned r=0;r<2;++r)for(unsigned c=0;c<5;++c){
  __CPROVER_assert(copy[r*5+c]==original[r*5+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*2+r]==original[r*5+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=10)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_2x6() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,2,6);sage_cpp::transpose_kernel<uint64_t>(a,out,2,6);
 for(unsigned r=0;r<2;++r)for(unsigned c=0;c<6;++c){
  __CPROVER_assert(copy[r*6+c]==original[r*6+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*2+r]==original[r*6+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=12)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_2x7() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,2,7);sage_cpp::transpose_kernel<uint64_t>(a,out,2,7);
 for(unsigned r=0;r<2;++r)for(unsigned c=0;c<7;++c){
  __CPROVER_assert(copy[r*7+c]==original[r*7+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*2+r]==original[r*7+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=14)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_2x8() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,2,8);sage_cpp::transpose_kernel<uint64_t>(a,out,2,8);
 for(unsigned r=0;r<2;++r)for(unsigned c=0;c<8;++c){
  __CPROVER_assert(copy[r*8+c]==original[r*8+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*2+r]==original[r*8+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=16)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_3x1() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,3,1);sage_cpp::transpose_kernel<uint64_t>(a,out,3,1);
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<1;++c){
  __CPROVER_assert(copy[r*1+c]==original[r*1+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*3+r]==original[r*1+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=3)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_3x2() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,3,2);sage_cpp::transpose_kernel<uint64_t>(a,out,3,2);
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<2;++c){
  __CPROVER_assert(copy[r*2+c]==original[r*2+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*3+r]==original[r*2+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=6)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_3x3() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,3,3);sage_cpp::transpose_kernel<uint64_t>(a,out,3,3);
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<3;++c){
  __CPROVER_assert(copy[r*3+c]==original[r*3+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*3+r]==original[r*3+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=9)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_3x4() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,3,4);sage_cpp::transpose_kernel<uint64_t>(a,out,3,4);
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<4;++c){
  __CPROVER_assert(copy[r*4+c]==original[r*4+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*3+r]==original[r*4+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=12)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_3x5() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,3,5);sage_cpp::transpose_kernel<uint64_t>(a,out,3,5);
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<5;++c){
  __CPROVER_assert(copy[r*5+c]==original[r*5+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*3+r]==original[r*5+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=15)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_3x6() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,3,6);sage_cpp::transpose_kernel<uint64_t>(a,out,3,6);
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<6;++c){
  __CPROVER_assert(copy[r*6+c]==original[r*6+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*3+r]==original[r*6+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=18)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_3x7() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,3,7);sage_cpp::transpose_kernel<uint64_t>(a,out,3,7);
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<7;++c){
  __CPROVER_assert(copy[r*7+c]==original[r*7+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*3+r]==original[r*7+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=21)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_3x8() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,3,8);sage_cpp::transpose_kernel<uint64_t>(a,out,3,8);
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<8;++c){
  __CPROVER_assert(copy[r*8+c]==original[r*8+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*3+r]==original[r*8+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=24)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_4x1() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,4,1);sage_cpp::transpose_kernel<uint64_t>(a,out,4,1);
 for(unsigned r=0;r<4;++r)for(unsigned c=0;c<1;++c){
  __CPROVER_assert(copy[r*1+c]==original[r*1+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*4+r]==original[r*1+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=4)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_4x2() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,4,2);sage_cpp::transpose_kernel<uint64_t>(a,out,4,2);
 for(unsigned r=0;r<4;++r)for(unsigned c=0;c<2;++c){
  __CPROVER_assert(copy[r*2+c]==original[r*2+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*4+r]==original[r*2+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=8)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_4x3() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,4,3);sage_cpp::transpose_kernel<uint64_t>(a,out,4,3);
 for(unsigned r=0;r<4;++r)for(unsigned c=0;c<3;++c){
  __CPROVER_assert(copy[r*3+c]==original[r*3+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*4+r]==original[r*3+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=12)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_4x4() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,4,4);sage_cpp::transpose_kernel<uint64_t>(a,out,4,4);
 for(unsigned r=0;r<4;++r)for(unsigned c=0;c<4;++c){
  __CPROVER_assert(copy[r*4+c]==original[r*4+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*4+r]==original[r*4+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=16)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_4x5() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,4,5);sage_cpp::transpose_kernel<uint64_t>(a,out,4,5);
 for(unsigned r=0;r<4;++r)for(unsigned c=0;c<5;++c){
  __CPROVER_assert(copy[r*5+c]==original[r*5+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*4+r]==original[r*5+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=20)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_4x6() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,4,6);sage_cpp::transpose_kernel<uint64_t>(a,out,4,6);
 for(unsigned r=0;r<4;++r)for(unsigned c=0;c<6;++c){
  __CPROVER_assert(copy[r*6+c]==original[r*6+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*4+r]==original[r*6+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=24)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_4x7() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,4,7);sage_cpp::transpose_kernel<uint64_t>(a,out,4,7);
 for(unsigned r=0;r<4;++r)for(unsigned c=0;c<7;++c){
  __CPROVER_assert(copy[r*7+c]==original[r*7+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*4+r]==original[r*7+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=28)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_4x8() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,4,8);sage_cpp::transpose_kernel<uint64_t>(a,out,4,8);
 for(unsigned r=0;r<4;++r)for(unsigned c=0;c<8;++c){
  __CPROVER_assert(copy[r*8+c]==original[r*8+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*4+r]==original[r*8+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=32)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_5x1() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,5,1);sage_cpp::transpose_kernel<uint64_t>(a,out,5,1);
 for(unsigned r=0;r<5;++r)for(unsigned c=0;c<1;++c){
  __CPROVER_assert(copy[r*1+c]==original[r*1+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*5+r]==original[r*1+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=5)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_5x2() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,5,2);sage_cpp::transpose_kernel<uint64_t>(a,out,5,2);
 for(unsigned r=0;r<5;++r)for(unsigned c=0;c<2;++c){
  __CPROVER_assert(copy[r*2+c]==original[r*2+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*5+r]==original[r*2+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=10)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_5x3() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,5,3);sage_cpp::transpose_kernel<uint64_t>(a,out,5,3);
 for(unsigned r=0;r<5;++r)for(unsigned c=0;c<3;++c){
  __CPROVER_assert(copy[r*3+c]==original[r*3+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*5+r]==original[r*3+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=15)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_5x4() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,5,4);sage_cpp::transpose_kernel<uint64_t>(a,out,5,4);
 for(unsigned r=0;r<5;++r)for(unsigned c=0;c<4;++c){
  __CPROVER_assert(copy[r*4+c]==original[r*4+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*5+r]==original[r*4+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=20)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_5x5() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,5,5);sage_cpp::transpose_kernel<uint64_t>(a,out,5,5);
 for(unsigned r=0;r<5;++r)for(unsigned c=0;c<5;++c){
  __CPROVER_assert(copy[r*5+c]==original[r*5+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*5+r]==original[r*5+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=25)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_5x6() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,5,6);sage_cpp::transpose_kernel<uint64_t>(a,out,5,6);
 for(unsigned r=0;r<5;++r)for(unsigned c=0;c<6;++c){
  __CPROVER_assert(copy[r*6+c]==original[r*6+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*5+r]==original[r*6+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=30)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_5x7() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,5,7);sage_cpp::transpose_kernel<uint64_t>(a,out,5,7);
 for(unsigned r=0;r<5;++r)for(unsigned c=0;c<7;++c){
  __CPROVER_assert(copy[r*7+c]==original[r*7+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*5+r]==original[r*7+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=35)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_5x8() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,5,8);sage_cpp::transpose_kernel<uint64_t>(a,out,5,8);
 for(unsigned r=0;r<5;++r)for(unsigned c=0;c<8;++c){
  __CPROVER_assert(copy[r*8+c]==original[r*8+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*5+r]==original[r*8+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=40)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_6x1() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,6,1);sage_cpp::transpose_kernel<uint64_t>(a,out,6,1);
 for(unsigned r=0;r<6;++r)for(unsigned c=0;c<1;++c){
  __CPROVER_assert(copy[r*1+c]==original[r*1+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*6+r]==original[r*1+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=6)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_6x2() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,6,2);sage_cpp::transpose_kernel<uint64_t>(a,out,6,2);
 for(unsigned r=0;r<6;++r)for(unsigned c=0;c<2;++c){
  __CPROVER_assert(copy[r*2+c]==original[r*2+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*6+r]==original[r*2+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=12)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_6x3() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,6,3);sage_cpp::transpose_kernel<uint64_t>(a,out,6,3);
 for(unsigned r=0;r<6;++r)for(unsigned c=0;c<3;++c){
  __CPROVER_assert(copy[r*3+c]==original[r*3+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*6+r]==original[r*3+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=18)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_6x4() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,6,4);sage_cpp::transpose_kernel<uint64_t>(a,out,6,4);
 for(unsigned r=0;r<6;++r)for(unsigned c=0;c<4;++c){
  __CPROVER_assert(copy[r*4+c]==original[r*4+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*6+r]==original[r*4+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=24)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_6x5() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,6,5);sage_cpp::transpose_kernel<uint64_t>(a,out,6,5);
 for(unsigned r=0;r<6;++r)for(unsigned c=0;c<5;++c){
  __CPROVER_assert(copy[r*5+c]==original[r*5+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*6+r]==original[r*5+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=30)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_6x6() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,6,6);sage_cpp::transpose_kernel<uint64_t>(a,out,6,6);
 for(unsigned r=0;r<6;++r)for(unsigned c=0;c<6;++c){
  __CPROVER_assert(copy[r*6+c]==original[r*6+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*6+r]==original[r*6+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=36)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_6x7() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,6,7);sage_cpp::transpose_kernel<uint64_t>(a,out,6,7);
 for(unsigned r=0;r<6;++r)for(unsigned c=0;c<7;++c){
  __CPROVER_assert(copy[r*7+c]==original[r*7+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*6+r]==original[r*7+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=42)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_6x8() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,6,8);sage_cpp::transpose_kernel<uint64_t>(a,out,6,8);
 for(unsigned r=0;r<6;++r)for(unsigned c=0;c<8;++c){
  __CPROVER_assert(copy[r*8+c]==original[r*8+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*6+r]==original[r*8+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=48)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_7x1() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,7,1);sage_cpp::transpose_kernel<uint64_t>(a,out,7,1);
 for(unsigned r=0;r<7;++r)for(unsigned c=0;c<1;++c){
  __CPROVER_assert(copy[r*1+c]==original[r*1+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*7+r]==original[r*1+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=7)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_7x2() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,7,2);sage_cpp::transpose_kernel<uint64_t>(a,out,7,2);
 for(unsigned r=0;r<7;++r)for(unsigned c=0;c<2;++c){
  __CPROVER_assert(copy[r*2+c]==original[r*2+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*7+r]==original[r*2+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=14)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_7x3() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,7,3);sage_cpp::transpose_kernel<uint64_t>(a,out,7,3);
 for(unsigned r=0;r<7;++r)for(unsigned c=0;c<3;++c){
  __CPROVER_assert(copy[r*3+c]==original[r*3+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*7+r]==original[r*3+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=21)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_7x4() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,7,4);sage_cpp::transpose_kernel<uint64_t>(a,out,7,4);
 for(unsigned r=0;r<7;++r)for(unsigned c=0;c<4;++c){
  __CPROVER_assert(copy[r*4+c]==original[r*4+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*7+r]==original[r*4+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=28)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_7x5() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,7,5);sage_cpp::transpose_kernel<uint64_t>(a,out,7,5);
 for(unsigned r=0;r<7;++r)for(unsigned c=0;c<5;++c){
  __CPROVER_assert(copy[r*5+c]==original[r*5+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*7+r]==original[r*5+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=35)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_7x6() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,7,6);sage_cpp::transpose_kernel<uint64_t>(a,out,7,6);
 for(unsigned r=0;r<7;++r)for(unsigned c=0;c<6;++c){
  __CPROVER_assert(copy[r*6+c]==original[r*6+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*7+r]==original[r*6+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=42)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_7x7() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,7,7);sage_cpp::transpose_kernel<uint64_t>(a,out,7,7);
 for(unsigned r=0;r<7;++r)for(unsigned c=0;c<7;++c){
  __CPROVER_assert(copy[r*7+c]==original[r*7+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*7+r]==original[r*7+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=49)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_7x8() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,7,8);sage_cpp::transpose_kernel<uint64_t>(a,out,7,8);
 for(unsigned r=0;r<7;++r)for(unsigned c=0;c<8;++c){
  __CPROVER_assert(copy[r*8+c]==original[r*8+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*7+r]==original[r*8+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=56)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_8x1() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,8,1);sage_cpp::transpose_kernel<uint64_t>(a,out,8,1);
 for(unsigned r=0;r<8;++r)for(unsigned c=0;c<1;++c){
  __CPROVER_assert(copy[r*1+c]==original[r*1+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*8+r]==original[r*1+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=8)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_8x2() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,8,2);sage_cpp::transpose_kernel<uint64_t>(a,out,8,2);
 for(unsigned r=0;r<8;++r)for(unsigned c=0;c<2;++c){
  __CPROVER_assert(copy[r*2+c]==original[r*2+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*8+r]==original[r*2+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=16)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_8x3() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,8,3);sage_cpp::transpose_kernel<uint64_t>(a,out,8,3);
 for(unsigned r=0;r<8;++r)for(unsigned c=0;c<3;++c){
  __CPROVER_assert(copy[r*3+c]==original[r*3+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*8+r]==original[r*3+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=24)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_8x4() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,8,4);sage_cpp::transpose_kernel<uint64_t>(a,out,8,4);
 for(unsigned r=0;r<8;++r)for(unsigned c=0;c<4;++c){
  __CPROVER_assert(copy[r*4+c]==original[r*4+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*8+r]==original[r*4+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=32)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_8x5() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,8,5);sage_cpp::transpose_kernel<uint64_t>(a,out,8,5);
 for(unsigned r=0;r<8;++r)for(unsigned c=0;c<5;++c){
  __CPROVER_assert(copy[r*5+c]==original[r*5+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*8+r]==original[r*5+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=40)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_8x6() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,8,6);sage_cpp::transpose_kernel<uint64_t>(a,out,8,6);
 for(unsigned r=0;r<8;++r)for(unsigned c=0;c<6;++c){
  __CPROVER_assert(copy[r*6+c]==original[r*6+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*8+r]==original[r*6+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=48)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_8x7() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,8,7);sage_cpp::transpose_kernel<uint64_t>(a,out,8,7);
 for(unsigned r=0;r<8;++r)for(unsigned c=0;c<7;++c){
  __CPROVER_assert(copy[r*7+c]==original[r*7+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*8+r]==original[r*7+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=56)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
void layout_8x8() {
 uint64_t a[64],original[64],copy[64],out[64];
 for(unsigned i=0;i<64;++i){a[i]=nondet_u64();original[i]=a[i];copy[i]=0;out[i]=0;}
 sage_cpp::copy_kernel<uint64_t>(a,copy,8,8);sage_cpp::transpose_kernel<uint64_t>(a,out,8,8);
 for(unsigned r=0;r<8;++r)for(unsigned c=0;c<8;++c){
  __CPROVER_assert(copy[r*8+c]==original[r*8+c],"copy preserves all 64 bits");
  __CPROVER_assert(out[c*8+r]==original[r*8+c],"transpose preserves all 64 bits");
 }
 for(unsigned i=0;i<64;++i){
  __CPROVER_assert(a[i]==original[i],"input unchanged");
  if(i>=64)__CPROVER_assert(copy[i]==0 && out[i]==0,"inactive outputs unchanged");
 }
}
