import { useEffect, useRef, useSyncExternalStore } from "react";

type Cleanup = void | (() => void);
type LifecycleCallback = () => Cleanup;
type WatchCallback = (value: any, previousValue: any) => void;

type LifecycleContext = {
  mounted: LifecycleCallback[];
  beforeUnmount: LifecycleCallback[];
  watchers: Set<() => void>;
  listeners: Set<() => void>;
  version: number;
  pending: boolean;
  notify: () => void;
  subscribe: (listener: () => void) => () => void;
  getSnapshot: () => number;
};

let activeContext: LifecycleContext | null = null;
const proxyCache = new WeakMap<object, any>();

function createLifecycleContext(): LifecycleContext {
  const context: LifecycleContext = {
    mounted: [],
    beforeUnmount: [],
    watchers: new Set(),
    listeners: new Set(),
    version: 0,
    pending: false,
    notify() {
      if (context.pending) {
        return;
      }
      context.pending = true;
      const schedule =
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

function currentContext() {
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

function toComparable(value: any) {
  if (Array.isArray(value)) {
    return value.slice();
  }
  return value;
}

function hasChanged(left: any, right: any) {
  if (Array.isArray(left) && Array.isArray(right)) {
    if (left.length !== right.length) {
      return true;
    }
    return left.some((item, index) => !Object.is(item, right[index]));
  }
  return !Object.is(left, right);
}

function proxied<T extends object>(target: T, context: LifecycleContext): T {
  const cached = proxyCache.get(target);
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

  proxyCache.set(target, proxy);
  return proxy;
}

export function ref<T>(initialValue: T) {
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

export function silentRef<T>(initialValue: T) {
  let innerValue = initialValue;
  return {
    get value() {
      return innerValue;
    },
    set value(nextValue) {
      innerValue = nextValue;
    },
  };
}

export function reactive<T extends object>(target: T): T {
  return proxied(target, currentContext());
}

export function computed<T>(factory: () => T) {
  return {
    get value() {
      return factory();
    },
  };
}

export function watch(source: any, callback: WatchCallback, options: { immediate?: boolean } = {}) {
  const context = currentContext();
  const read = () => (typeof source === "function" ? source() : source?.value);
  let previous = toComparable(read());

  if (options.immediate) {
    callback(read(), undefined);
    previous = toComparable(read());
  }

  const runner = () => {
    const next = toComparable(read());
    if (!hasChanged(next, previous)) {
      return;
    }
    const oldValue = previous;
    previous = Array.isArray(next) ? next.slice() : next;
    callback(read(), oldValue);
  };
  context.watchers.add(runner);
  return () => {
    context.watchers.delete(runner);
  };
}

export function nextTick(callback?: () => void) {
  const promise = Promise.resolve();
  if (callback) {
    return promise.then(callback);
  }
  return promise;
}

export function onMounted(callback: LifecycleCallback) {
  currentContext().mounted.push(callback);
}

export function onBeforeUnmount(callback: LifecycleCallback) {
  currentContext().beforeUnmount.push(callback);
}

export function useReactiveStore<T extends object>(factory: () => T): T {
  const storeRef = useRef<{ context: LifecycleContext; store: T; cleanups: Cleanup[] } | null>(null);
  if (!storeRef.current) {
    const context = createLifecycleContext();
    const store = withLifecycle(context, factory);
    storeRef.current = { context, store, cleanups: [] };
  }

  const { context, store } = storeRef.current;
  useSyncExternalStore(context.subscribe, context.getSnapshot, context.getSnapshot);

  useEffect(() => {
    const cleanups = context.mounted.map((callback) => callback()).filter(Boolean);
    storeRef.current!.cleanups = cleanups;
    return () => {
      for (const cleanup of storeRef.current?.cleanups || []) {
        if (typeof cleanup === "function") {
          cleanup();
        }
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
  }, [context]);

  return store;
}
