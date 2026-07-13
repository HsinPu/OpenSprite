import { useEffect, useRef, useSyncExternalStore } from "react";

type Cleanup = void | (() => void);
type RegisteredCleanup = () => void;
type LifecycleCallback = () => Cleanup;
type RefLike<T> = { value: T };
type ReadonlyRefLike<T> = { readonly value: T };
type WatchCallback<T> = (value: T, previousValue: T | undefined) => void;
type WatchSource<T> = ReadonlyRefLike<T> | (() => T);
type WatchOptions = { immediate?: boolean };
type WatchStopHandle = () => void;
type WatchRunner = () => void;
type StoreListener = () => void;
type StoreSubscription = () => void;
type Scheduler = (callback: StoreListener) => void;
type ProxyCache = WeakMap<object, object>;

type LifecycleContext = {
  readonly mounted: LifecycleCallback[];
  readonly beforeUnmount: LifecycleCallback[];
  readonly watchers: Set<WatchRunner>;
  readonly listeners: Set<StoreListener>;
  version: number;
  pending: boolean;
  readonly proxyCache: ProxyCache;
  readonly notify: () => void;
  readonly subscribe: (listener: StoreListener) => StoreSubscription;
  readonly getSnapshot: () => number;
};
type ReactiveStoreEntry<T extends object> = {
  readonly context: LifecycleContext;
  readonly store: T;
  cleanups: RegisteredCleanup[];
};

let activeContext: LifecycleContext | null = null;

function createLifecycleContext(): LifecycleContext {
  const context: LifecycleContext = {
    mounted: [],
    beforeUnmount: [],
    watchers: new Set(),
    listeners: new Set(),
    version: 0,
    pending: false,
    proxyCache: new WeakMap(),
    notify() {
      if (context.pending) {
        return;
      }
      context.pending = true;
      const schedule: Scheduler =
        typeof requestAnimationFrame === "function"
          ? (callback: () => void) => requestAnimationFrame(() => callback())
          : (callback: () => void) => setTimeout(callback, 0);
      schedule(() => {
        context.pending = false;
        context.version += 1;
        for (const watcher of Array.from(context.watchers)) {
          watcher();
        }
        for (const listener of Array.from(context.listeners)) {
          listener();
        }
      });
    },
    subscribe(listener) {
      context.listeners.add(listener);
      return () => {
        context.listeners.delete(listener);
      };
    },
    getSnapshot() {
      return context.version;
    },
  };
  return context;
}

function currentContext(): LifecycleContext {
  if (!activeContext) {
    activeContext = createLifecycleContext();
  }
  return activeContext;
}

function withLifecycle<T>(context: LifecycleContext, factory: () => T): T {
  const previousContext = activeContext;
  activeContext = context;
  try {
    return factory();
  } finally {
    activeContext = previousContext;
  }
}

function isObject(value: unknown): value is object {
  return Boolean(value) && typeof value === "object";
}

function isProxyable(value: unknown): value is object {
  if (!isObject(value)) {
    return false;
  }
  if (Array.isArray(value)) {
    return true;
  }
  return Object.prototype.toString.call(value) === "[object Object]";
}

function toComparable<T>(value: T): T;
function toComparable(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.slice();
  }
  return value;
}

function hasChanged(left: unknown, right: unknown): boolean {
  if (Array.isArray(left) && Array.isArray(right)) {
    if (left.length !== right.length) {
      return true;
    }
    return left.some((item, index) => !Object.is(item, right[index]));
  }
  return !Object.is(left, right);
}

function isRegisteredCleanup(value: Cleanup): value is RegisteredCleanup {
  return typeof value === "function";
}

function proxied<T extends object>(target: T, context: LifecycleContext): T;
function proxied(target: object, context: LifecycleContext): object {
  const cached = context.proxyCache.get(target);
  if (cached) {
    return cached;
  }

  const proxy = new Proxy(target, {
    get(source, property, receiver) {
      const value = Reflect.get(source, property, receiver);
      return isProxyable(value) ? proxied(value, context) : value;
    },
    set(source, property, value, receiver) {
      const previous = Reflect.get(source, property, receiver);
      const changed = !Object.is(previous, value);
      const result = Reflect.set(source, property, value, receiver);
      if (changed) {
        context.notify();
      }
      return result;
    },
    deleteProperty(source, property) {
      const hadProperty = Reflect.has(source, property);
      const result = Reflect.deleteProperty(source, property);
      if (hadProperty) {
        context.notify();
      }
      return result;
    },
  });

  context.proxyCache.set(target, proxy);
  return proxy;
}

export function ref<T>(initialValue: T): RefLike<T> {
  const context = currentContext();
  let innerValue = isProxyable(initialValue) ? proxied(initialValue, context) : initialValue;
  return {
    get value() {
      return innerValue;
    },
    set value(nextValue) {
      const involvesOpaqueObject =
        (isObject(innerValue) && !isProxyable(innerValue)) || (isObject(nextValue) && !isProxyable(nextValue));
      const normalizedValue = isProxyable(nextValue) ? proxied(nextValue, context) : nextValue;
      if (!Object.is(innerValue, normalizedValue)) {
        innerValue = normalizedValue;
        if (!involvesOpaqueObject) {
          context.notify();
        }
      }
    },
  };
}

export function reactive<T extends object>(target: T): T {
  return proxied(target, currentContext());
}

export function computed<T>(factory: () => T): ReadonlyRefLike<T> {
  return {
    get value() {
      return factory();
    },
  };
}

export function watch<T>(source: WatchSource<T>, callback: WatchCallback<T>, options: WatchOptions = {}): WatchStopHandle {
  const context = currentContext();
  const read: () => T = () => (typeof source === "function" ? source() : source.value);
  let previous = toComparable(read());

  if (options.immediate) {
    callback(read(), undefined);
    previous = toComparable(read());
  }

  const runner: WatchRunner = () => {
    const next = toComparable(read());
    if (!hasChanged(next, previous)) {
      return;
    }
    const oldValue = previous;
    previous = next;
    callback(read(), oldValue);
  };
  context.watchers.add(runner);
  return () => {
    context.watchers.delete(runner);
  };
}

export function onMounted(callback: LifecycleCallback): void {
  currentContext().mounted.push(callback);
}

export function onBeforeUnmount(callback: LifecycleCallback): void {
  currentContext().beforeUnmount.push(callback);
}

export function useReactiveStore<T extends object>(factory: () => T): T {
  const storeRef = useRef<ReactiveStoreEntry<T> | null>(null);
  if (!storeRef.current) {
    const context = createLifecycleContext();
    const store = withLifecycle(context, factory);
    storeRef.current = { context, store, cleanups: [] };
  }

  const entry = storeRef.current;
  const { context, store } = entry;
  useSyncExternalStore(context.subscribe, context.getSnapshot, context.getSnapshot);

  useEffect(() => {
    entry.cleanups = context.mounted.map((callback) => callback()).filter(isRegisteredCleanup);
    return () => {
      for (const cleanup of entry.cleanups) {
        cleanup();
      }
      for (const callback of context.beforeUnmount) {
        const cleanup = callback();
        if (typeof cleanup === "function") {
          cleanup();
        }
      }
      context.watchers.clear();
      context.listeners.clear();
    };
  }, [context, entry]);

  return store;
}
