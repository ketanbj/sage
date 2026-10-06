#pragma once
typedef unsigned __int128 Code;
inline unsigned length(Code code) {unsigned n=1;while(code>=64){code>>=6;++n;}return n;}
inline Code leaf(unsigned i) {__CPROVER_assert(i<32,"leaf index bounded");return Code(i+2);}
struct ExpressionArithmetic {
 static Code join(Code a,Code b,unsigned op) {
  unsigned al=length(a),bl=length(b),len=al+bl+1;
  __CPROVER_assert(len<=21,"expression encoding does not overflow");
  return (Code(op)<<((len-1)*6))|(a<<(bl*6))|b;
 }
 static Code add(Code a,Code b){return join(a,b,60);}
 static Code multiply(Code a,Code b){return join(a,b,61);}
};
inline Code expected(unsigned op,unsigned m,unsigned k,unsigned n,unsigned r,unsigned c) {
 unsigned tokens[21];unsigned count=0;unsigned a=r*k+c+2,b=r*k+c+18;
 switch(op) {
 case 0:tokens[count++]=a;break;
 case 1:tokens[count++]=60;tokens[count++]=a;tokens[count++]=b;break;
 case 2:tokens[count++]=61;tokens[count++]=a;tokens[count++]=b;break;
 case 3:tokens[count++]=c*k+r+2;break;
 case 4:
  for(unsigned p=0;p<k;++p)tokens[count++]=60;
  tokens[count++]=0;
  for(unsigned p=0;p<k;++p){tokens[count++]=61;tokens[count++]=r*k+p+2;tokens[count++]=p*n+c+18;}
  break;
 case 5:tokens[count++]=61;tokens[count++]=18;tokens[count++]=a;break;
 }
 __CPROVER_assert(count<=21,"specification encoding bounded");
 Code code=0;for(unsigned i=0;i<count;++i)code=(code<<6)|tokens[i];return code;
}
