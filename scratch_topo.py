import numpy as np

# ---- synthetic prob map: 2 robust lakes + 1 speckle ----
H=W=120
P=np.zeros((H,W),np.float32)
yy,xx=np.mgrid[0:H,0:W]
def blob(cy,cx,r,amp):
    return amp*np.exp(-((yy-cy)**2+(xx-cx)**2)/(2*r*r))
P+=blob(35,35,12,0.95)      # strong lake A
P+=blob(75,85,10,0.88)      # strong lake B
P+=blob(20,95,4,0.55)       # weak speckle
rng=np.random.default_rng(0)
P+=rng.normal(0,0.04,(H,W)).astype(np.float32)  # noise -> many tiny maxima
P=np.clip(P,0,1)

# ============ H0 superlevel persistence via union-find ============
def superlevel_persistence(P):
    H,W=P.shape
    order=np.argsort(-P.ravel())          # high P first
    parent=np.full(H*W,-1,np.int64)
    birth=np.zeros(H*W,np.float32)        # peak P of component root
    label=np.full(H*W,-1,np.int64)        # pixel -> root id (owning peak)
    pairs=[]                              # (birth, death) persistence pairs
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]; x=parent[x]
        return x
    nb=[-W,W,-1,1]                        # 4-connectivity
    activated=np.zeros(H*W,bool)
    for idx in order:
        y,x=divmod(idx,W)
        parent[idx]=idx; birth[idx]=P.ravel()[idx]; label[idx]=idx
        activated[idx]=True
        roots=set()
        for d,(dy,dx) in zip(nb,[(-1,0),(1,0),(0,-1),(0,1)]):
            ny,nx=y+dy,x+dx
            if 0<=ny<H and 0<=nx<W:
                j=ny*W+nx
                if activated[j]:
                    roots.add(find(j))
        roots.add(idx)
        roots=list(roots)
        if len(roots)>1:
            # merge: highest-birth root survives, others die at P(idx)
            roots.sort(key=lambda r:-birth[r])
            keep=roots[0]
            for r in roots[1:]:
                if r!=keep:
                    pairs.append((birth[r], P.ravel()[idx]))  # (peak, saddle)
                    parent[r]=keep
            # propagate keep birth
    # remaining roots = never died -> death at global min
    gmin=float(P.min())
    final_roots=set(find(i) for i in range(H*W))
    for r in final_roots:
        pairs.append((birth[r], gmin))
    # build persistence-of-peak map: each pixel -> persistence of its FINAL root's peak
    # recompute persistence per root
    pers_of_root={}
    # death of a root = the saddle at which it merged; for survivors = gmin
    # easier: assign each pixel persistence = birth(finalroot) - death(when it merged)
    # We'll recompute via second pass: map every pixel to final root, persistence = peak-? 
    return np.array(pairs), find, label

pairs,find,label=superlevel_persistence(P)
pers=pairs[:,0]-pairs[:,1]
ord_=np.argsort(-pers)
print("top persistences (peak, saddle, persistence):")
for i in ord_[:6]:
    print(f"  peak={pairs[i,0]:.3f} death={pairs[i,1]:.3f} pers={pers[i]:.3f}")
print("n features:",len(pers), " >0.3:",int((pers>0.3).sum()), " gap candidates sorted:",np.round(np.sort(pers)[::-1][:8],3))

# ============ cross-check with gudhi cubical ============
import gudhi
cc=gudhi.CubicalComplex(top_dimensional_cells=(-P))  # sublevel of -P = superlevel of P
cc.persistence()
d0=cc.persistence_intervals_in_dimension(0)
g_pers=np.sort((-d0[:,0]) - (-d0[np.isfinite(d0[:,1])][:,1]) if False else (-(d0[:,0]))-(-(np.where(np.isfinite(d0[:,1]),d0[:,1],0))))[::-1]
# birth=-peak, death=-saddle ; persistence = death-birth in -P = peak-saddle
gp=(-d0[:,0])-(-np.where(np.isfinite(d0[:,1]),d0[:,1],0.0))
print("gudhi H0 top persistences:",np.round(np.sort(gp)[::-1][:6],3))
d1=cc.persistence_intervals_in_dimension(1)
print("gudhi H1 count (loops):",len(d1))
