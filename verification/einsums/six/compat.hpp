namespace std {
typedef unsigned long size_t;
struct invalid_argument { invalid_argument(const char*) {} };
struct out_of_range { out_of_range(const char*) {} };
struct array {
 SCALAR a[16];
 SCALAR* begin() {return a;} SCALAR* data() {return a;} const SCALAR* data() const {return a;}
 SCALAR& operator[](size_t i) {return a[i];} SCALAR operator[](size_t i) const {return a[i];}
};
struct span {
 const SCALAR* p; size_t n;
 span(const SCALAR* p_, size_t n_) : p(p_), n(n_) {}
 size_t size() const {return n;}
 const SCALAR* begin() const {return p;} const SCALAR* end() const {return p+n;}
};
inline void copy(const SCALAR* begin,const SCALAR* end,SCALAR* out) {
 while(begin!=end) { *out=*begin; ++out; ++begin; }
}
}
